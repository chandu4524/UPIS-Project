"""
Universal CSV header normalization and optional column canonicalization.

All canonical fields are optional — missing headers never block upload.
Matching: exact normalized match first, then fuzzy (SequenceMatcher).
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Fields used for citizen import + staging (informational "required" list only).
CORE_IMPORT_COLUMNS = ["full_name", "mobile", "district", "village", "dob"]

# Minimum similarity for fuzzy header match (0.0–1.0).
FUZZY_MATCH_THRESHOLD = 0.82

# Universal optional canonical fields → alias variants (lowercase/spacing normalized at runtime).
UNIVERSAL_HEADER_ALIASES: Dict[str, List[str]] = {
  "full_name": [
    "full_name", "full name", "fullname", "name", "citizen_name", "beneficiary_name",
    "customer_name", "consumer_name", "person_name", "employee_name", "account_holder",
    "applicant_name", "bank_customer_name", "electricity_consumer", "gas_consumer_name",
    "subscriber_name", "member_name", "resident_name", "patient_name",
  ],
  "mobile": [
    "mobile", "mobile_no", "mobile_number", "mobileno", "phone", "phone_no", "phone_number",
    "contact", "contact_no", "contact_number", "msisdn", "cell", "cellphone", "telephone",
    "tel", "whatsapp", "whatsapp_no",
  ],
  "district": [
    "district", "district_name", "dist", "city", "city_name", "division", "region",
  ],
  "village": [
    "village", "village_name", "gram", "grama", "gram_panchayat", "panchayat", "town",
    "area", "locality", "location", "habitation", "village/town", "mandal", "block",
  ],
  "dob": [
    "dob", "date_of_birth", "date of birth", "birth_date", "birthdate", "birth date",
    "age_dob", "d.o.b", "dob_date",
  ],
  "age": [
    "age", "age_years", "age years", "years", "age_in_years",
  ],
  "gender": [
    "gender", "sex", "m_f", "male_female",
  ],
  "father_name": [
    "father_name", "father name", "fathers_name", "father", "father_or_husband_name",
    "parent_name", "guardian_name", "guardian",
  ],
  "spouse_name": [
    "spouse_name", "spouse name", "spouse", "husband_name", "wife_name", "partner_name",
  ],
  "husband_name": ["husband_name", "husband name", "husband"],
  "wife_name": ["wife_name", "wife name", "wife"],
  "address": [
    "address", "full_address", "residential_address", "permanent_address", "present_address",
    "communication_address", "street", "street_address", "house_address",
  ],
  "pincode": ["pincode", "pin_code", "postal_code", "zip", "zipcode"],
  "aadhaar": [
    "aadhaar", "aadhaar_no", "aadhaar_number", "aadhar", "aadhar_no", "aadhaar_ref",
    "uid", "uidai",
  ],
  "pan": ["pan", "pan_no", "pan_number", "pan_card"],
  "voter_id": ["voter_id", "voter id", "epic", "epic_no", "voter_card"],
  "employee_id": ["employee_id", "employee id", "emp_id", "staff_id", "personnel_id"],
  "consumer_id": ["consumer_id", "consumer id", "consumer_no", "consumer_number"],
  "customer_id": ["customer_id", "customer id", "cust_id", "client_id"],
  "account_no": [
    "account_no", "account_number", "account number", "bank_account", "bank_account_no",
    "sb_account", "account",
  ],
  "ration_card": ["ration_card", "ration_card_no", "ration card", "rc_no"],
  "employer": ["employer", "employer_name", "company", "company_name", "organization"],
  "department": ["department", "dept", "department_name", "office", "wing"],
  "bank_name": ["bank_name", "bank name", "bank", "bank_branch"],
  "scheme_name": ["scheme_name", "scheme name", "scheme", "programme", "program", "welfare_scheme"],
  "utility_type": ["utility_type", "utility type", "service_type", "connection_type"],
  "connection_no": [
    "connection_no", "connection_number", "connection id", "service_no", "service_number",
    "electricity_service_no", "gas_connection_id", "meter_no", "consumer_number",
  ],
  "benefit_amount": ["benefit_amount", "benefit amount", "amount", "subsidy_amount"],
  "last_benefit_date": ["last_benefit_date", "last benefit date", "benefit_date"],
  "source_note": ["source_note", "source note", "remarks", "notes", "comments"],
}


def normalize_header(header: object) -> str:
    """
    Fuzzy-friendly normalization:
    - lowercase, trim
    - spaces, hyphens, slashes → underscore
    - remove other punctuation
    - collapse repeated underscores
    """
    s = "" if header is None else str(header)
    s = s.strip().lower()
    s = re.sub(r"[\s\-/\\]+", "_", s)
    s = re.sub(r"[^a-z0-9_]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _build_alias_lookup() -> Dict[str, str]:
    """normalized_alias -> canonical_field (first alias wins on collision)."""
    lookup: Dict[str, str] = {}
    for canonical, aliases in UNIVERSAL_HEADER_ALIASES.items():
        for alias in aliases:
            key = normalize_header(alias)
            if key and key not in lookup:
                lookup[key] = canonical
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def _score_header_match(normalized_col: str, normalized_alias: str) -> float:
    if not normalized_col or not normalized_alias:
        return 0.0
    if normalized_col == normalized_alias:
        return 1.0
    return SequenceMatcher(None, normalized_col, normalized_alias).ratio()


def match_column_to_canonical(normalized_col: str) -> Tuple[Optional[str], float]:
    """Return (canonical_field, score) for a single normalized header."""
    if not normalized_col:
        return None, 0.0

    if normalized_col in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[normalized_col], 1.0

    best_canonical: Optional[str] = None
    best_score = FUZZY_MATCH_THRESHOLD
    for alias_norm, canonical in _ALIAS_LOOKUP.items():
        score = _score_header_match(normalized_col, alias_norm)
        if score >= best_score:
            best_score = score
            best_canonical = canonical

    if best_canonical:
        return best_canonical, best_score
    return None, 0.0


def build_column_mapping(columns: List[object]) -> Dict[str, str]:
    """
    Map original column names → canonical field names.
    Greedy assignment: highest scores first; one canonical per column.
    """
    candidates: List[Tuple[str, str, float]] = []
    for col in columns:
        orig = "" if col is None else str(col)
        norm = normalize_header(orig)
        if not norm:
            continue
        for canonical, aliases in UNIVERSAL_HEADER_ALIASES.items():
            for alias in aliases:
                alias_norm = normalize_header(alias)
                score = _score_header_match(norm, alias_norm)
                if score >= FUZZY_MATCH_THRESHOLD:
                    candidates.append((orig, canonical, score))

    candidates.sort(key=lambda x: (-x[2], -len(normalize_header(x[0]))))

    mapping: Dict[str, str] = {}
    used_orig: set = set()
    used_canonical: set = set()
    for orig, canonical, _score in candidates:
        if orig in used_orig or canonical in used_canonical:
            continue
        mapping[orig] = canonical
        used_orig.add(orig)
        used_canonical.add(canonical)

    return mapping


def canonicalize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Rename dataframe columns to canonical names where a match exists."""
    mapping = build_column_mapping(list(df.columns))
    if not mapping:
        return df, {}
    return df.rename(columns=mapping), mapping


def validate_headers_informational(
    df: pd.DataFrame,
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """
    Returns (found_columns, missing_core_columns, column_mapping).
    missing_core_columns is informational only — never blocks upload.
    """
    _, mapping = canonicalize_columns(df)
    found = [str(c) for c in df.columns]
    missing = [c for c in CORE_IMPORT_COLUMNS if c not in df.columns]
    return found, missing, mapping
