"""Build dynamic 360-degree profiles from citizens, staging, and DuckDB uploads."""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.citizen import Citizen
from app.models.person_source import PersonSource
from app.models.person_staging import PersonStaging
from app.services.citizen_service import mobile_lookup_key
from app.services.header_canonicalization import UNIVERSAL_HEADER_ALIASES, normalize_header

SKIP_FIELD_KEYS = frozenset(
    {
        "matching_key",
        "normalized_name",
        "mobile_hash",
        "row_number",
        "upload_batch_id",
        "upload_id",
        "source_file",
        "uploaded_at",
        "department_name",
        "raw_content",
    }
)

CORE_FIELD_KEYS = frozenset(
    {"full_name", "mobile", "dob", "district", "village", "father_name", "spouse_name", "address"}
)


def _humanize_field(key: str) -> str:
    if not key:
        return "Field"
    if key in UNIVERSAL_HEADER_ALIASES:
        return key.replace("_", " ").title()
    return str(key).replace("_", " ").strip().title()


def _safe_json_loads(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _stringify_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and str(value) == "nan":
        return None
    text = str(value).strip()
    return text or None


def _collect_fields_from_mapping(
    mapping: Dict[str, Any],
    *,
    seen: Set[str],
) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    for key, value in mapping.items():
        canonical = normalize_header(key) or str(key)
        if canonical in SKIP_FIELD_KEYS:
            continue
        text = _stringify_value(value)
        if not text:
            continue
        dedupe_key = f"{canonical}:{text.lower()}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        fields.append(
            {
                "key": canonical,
                "label": _humanize_field(canonical),
                "value": text,
            }
        )
    return fields


def _section_key(source_name: str, department_name: str, upload_batch_id: Optional[int]) -> str:
    dept = (department_name or "").strip() or "GENERAL"
    src = (source_name or "").strip() or "Upload"
    batch = f"#{upload_batch_id}" if upload_batch_id else ""
    return f"{dept}::{src}::{batch}"


def _section_title(source_name: str, department_name: str) -> str:
    dept = (department_name or "").strip()
    src = (source_name or "").strip() or "Source upload"
    if dept and dept.upper() not in src.upper():
        return f"{dept} — {src}"
    return src


def _citizen_registry_section(citizen: Citizen) -> Dict[str, Any]:
    seen: Set[str] = set()
    fields = _collect_fields_from_mapping(
        {
            "full_name": citizen.full_name,
            "mobile": citizen.mobile,
            "dob": citizen.dob,
            "district": citizen.district,
            "village": citizen.village,
        },
        seen=seen,
    )
    for attr in ("father_name", "aadhaar", "aadhar", "pan", "address", "gender"):
        value = getattr(citizen, attr, None)
        if value:
            fields.extend(
                _collect_fields_from_mapping({attr: value}, seen=seen)
            )
    return {
        "section_id": "citizen_registry",
        "title": "Citizen registry",
        "source_type": "registry",
        "department_name": "GPIP",
        "source_name": "Citizen master",
        "upload_batch_id": None,
        "fields": fields,
        "field_count": len(fields),
    }


def _staging_to_section(row: PersonStaging) -> Dict[str, Any]:
    raw = _safe_json_loads(row.raw_json)
    normalized = _safe_json_loads(row.normalized_json)
    seen: Set[str] = set()
    fields = _collect_fields_from_mapping(normalized, seen=seen)
    fields.extend(_collect_fields_from_mapping(raw, seen=seen))

    return {
        "section_id": f"staging_{row.id}",
        "title": _section_title(row.source_name or "", row.department_name or ""),
        "source_type": "staging",
        "staging_id": row.id,
        "upload_batch_id": row.upload_batch_id,
        "source_name": row.source_name,
        "department_name": row.department_name,
        "row_number": row.row_number,
        "confidence_level": row.confidence_level,
        "extraction_status": row.extraction_status,
        "fields": fields,
        "field_count": len(fields),
    }


def _duckdb_row_to_section(
    row: Dict[str, Any],
    *,
    index: int,
) -> Dict[str, Any]:
    meta = {
        k: row.get(k)
        for k in ("upload_id", "source_file", "uploaded_at", "department_name")
        if row.get(k) not in (None, "")
    }
    seen: Set[str] = set()
    fields = _collect_fields_from_mapping(
        {k: v for k, v in row.items() if k not in meta},
        seen=seen,
    )
    dept = str(meta.get("department_name") or "GENERAL")
    src_file = str(meta.get("source_file") or "Uploaded file")
    return {
        "section_id": f"duckdb_{index}_{meta.get('upload_id', 0)}",
        "title": _section_title(src_file, dept),
        "source_type": "duckdb",
        "upload_id": meta.get("upload_id"),
        "source_file": meta.get("source_file"),
        "uploaded_at": meta.get("uploaded_at"),
        "department_name": dept,
        "fields": fields,
        "field_count": len(fields),
    }


def _fetch_linked_staging_rows(db: Session, citizen_id: int, citizen: Citizen) -> List[PersonStaging]:
    sources = (
        db.query(PersonSource)
        .filter(PersonSource.citizen_id == int(citizen_id))
        .all()
    )
    staging_ids = {int(s.staging_id) for s in sources if s.staging_id}
    upload_ids = {int(s.upload_batch_id) for s in sources if s.upload_batch_id}

    filters = []
    if staging_ids:
        filters.append(PersonStaging.id.in_(staging_ids))
    if upload_ids:
        filters.append(PersonStaging.upload_batch_id.in_(upload_ids))

    mobile_key = mobile_lookup_key(citizen.mobile)
    if mobile_key:
        filters.append(PersonStaging.mobile == mobile_key)

    if citizen.full_name:
        filters.append(PersonStaging.full_name.ilike(citizen.full_name.strip()))

    if not filters:
        return []

    rows = (
        db.query(PersonStaging)
        .filter(or_(*filters))
        .order_by(PersonStaging.created_at.desc(), PersonStaging.id.desc())
        .all()
    )

    seen_ids: Set[int] = set()
    unique: List[PersonStaging] = []
    for row in rows:
        if row.id in seen_ids:
            continue
        seen_ids.add(row.id)
        unique.append(row)
    return unique


def _fetch_duckdb_rows(citizen: Citizen, upload_ids: List[int]) -> List[Dict[str, Any]]:
    try:
        from app.services.duckdb_service import UPLOADED_DATA_TABLE, column_exists, execute_query, table_exists
    except Exception:
        return []

    if not table_exists(UPLOADED_DATA_TABLE):
        return []

    mobile_key = mobile_lookup_key(citizen.mobile)
    clauses: List[str] = []
    params: List[Any] = []

    if upload_ids:
        placeholders = ", ".join("?" for _ in upload_ids)
        clauses.append(f"upload_id IN ({placeholders})")
        params.extend(upload_ids)

    if mobile_key and column_exists(UPLOADED_DATA_TABLE, "mobile"):
        clauses.append("CAST(mobile AS VARCHAR) = ?")
        params.append(mobile_key)

    if citizen.full_name and column_exists(UPLOADED_DATA_TABLE, "full_name"):
        clauses.append("LOWER(CAST(full_name AS VARCHAR)) = LOWER(?)")
        params.append(str(citizen.full_name).strip())

    if not clauses:
        return []

    where_sql = " OR ".join(f"({c})" for c in clauses)
    sql = f"SELECT * FROM {UPLOADED_DATA_TABLE} WHERE {where_sql}"
    df = execute_query(sql, params)
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def _fetch_duckdb_rows_for_staging(row: PersonStaging) -> List[Dict[str, Any]]:
    """All DuckDB upload rows for this staging batch and matching identity (full history)."""
    try:
        from app.services.duckdb_service import UPLOADED_DATA_TABLE, column_exists, execute_query, table_exists
    except Exception:
        return []

    if not table_exists(UPLOADED_DATA_TABLE):
        return []

    clauses: List[str] = []
    params: List[Any] = []

    if row.upload_batch_id:
        clauses.append("upload_id = ?")
        params.append(int(row.upload_batch_id))

    mobile_key = mobile_lookup_key(row.mobile)
    if mobile_key and column_exists(UPLOADED_DATA_TABLE, "mobile"):
        clauses.append("CAST(mobile AS VARCHAR) = ?")
        params.append(mobile_key)

    if row.full_name and column_exists(UPLOADED_DATA_TABLE, "full_name"):
        clauses.append("LOWER(CAST(full_name AS VARCHAR)) = LOWER(?)")
        params.append(str(row.full_name).strip())

    if not clauses:
        return []

    where_sql = " OR ".join(f"({c})" for c in clauses)
    sql = f"SELECT * FROM {UPLOADED_DATA_TABLE} WHERE {where_sql}"
    df = execute_query(sql, params)
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def _fetch_duckdb_row_by_index(upload_id: int, row_index: int) -> Optional[Dict[str, Any]]:
    try:
        from app.services.duckdb_service import UPLOADED_DATA_TABLE, execute_query, table_exists
    except Exception:
        return None

    if not table_exists(UPLOADED_DATA_TABLE):
        return None

    df = execute_query(
        f"SELECT * FROM {UPLOADED_DATA_TABLE} WHERE upload_id = ?",
        [int(upload_id)],
    )
    if df is None or df.empty:
        return None
    records = df.to_dict(orient="records")
    idx = int(row_index)
    if idx < 0 or idx >= len(records):
        return None
    return records[idx]


def _citizen_id_for_staging(db: Session, staging_id: int) -> Optional[int]:
    link = (
        db.query(PersonSource)
        .filter(PersonSource.staging_id == int(staging_id))
        .order_by(PersonSource.id.desc())
        .first()
    )
    return int(link.citizen_id) if link and link.citizen_id else None


def build_staging_360_profile(db: Session, staging_id: int) -> Dict[str, Any]:
    """360 profile for an upload staging row (with or without citizen link)."""
    row = db.query(PersonStaging).filter(PersonStaging.id == int(staging_id)).first()
    if not row:
        return {}

    sections: List[Dict[str, Any]] = []
    citizen_id = _citizen_id_for_staging(db, staging_id)

    if citizen_id:
        citizen = db.query(Citizen).filter(Citizen.id == int(citizen_id)).first()
        if citizen:
            sections.append(_citizen_registry_section(citizen))
            sections.extend(
                s
                for s in (
                    _staging_to_section(r)
                    for r in _fetch_linked_staging_rows(db, citizen_id, citizen)
                )
                if s.get("staging_id") != row.id
            )

    sections.append(_staging_to_section(row))

    duckdb_records = _fetch_duckdb_rows_for_staging(row)
    for idx, record in enumerate(duckdb_records):
        sections.append(_duckdb_row_to_section(record, index=idx))

    all_field_keys: Set[str] = set()
    total_fields = 0
    for section in sections:
        total_fields += section.get("field_count", 0)
        for field in section.get("fields", []):
            all_field_keys.add(field.get("key", ""))

    return {
        "profile_type": "staging",
        "staging_id": row.id,
        "citizen_id": citizen_id,
        "sections": sections,
        "source_links": [],
        "linked_departments": [row.department_name] if row.department_name else [],
        "source_count": 1,
        "staging_row_count": 1,
        "duckdb_row_count": len(duckdb_records),
        "total_field_count": total_fields,
        "all_field_keys": sorted(k for k in all_field_keys if k),
    }


def build_duckdb_360_profile(db: Session, upload_id: int, row_index: int) -> Dict[str, Any]:
    """360 profile built from a single DuckDB uploaded_data row."""
    record = _fetch_duckdb_row_by_index(upload_id, row_index)
    if not record:
        return {}

    sections: List[Dict[str, Any]] = []
    staging_id = None
    citizen_id = None
    full_name = record.get("full_name")
    if full_name:
        match = (
            db.query(PersonStaging)
            .filter(
                PersonStaging.upload_batch_id == int(upload_id),
                PersonStaging.full_name.ilike(str(full_name).strip()),
            )
            .order_by(PersonStaging.id.desc())
            .first()
        )
        if match:
            staging_id = match.id
            citizen_id = _citizen_id_for_staging(db, staging_id)
            if citizen_id:
                citizen = db.query(Citizen).filter(Citizen.id == int(citizen_id)).first()
                if citizen:
                    sections.append(_citizen_registry_section(citizen))
            sections.append(_staging_to_section(match))

    sections.append(_duckdb_row_to_section(record, index=row_index))

    all_field_keys: Set[str] = set()
    total_fields = 0
    for section in sections:
        total_fields += section.get("field_count", 0)
        for field in section.get("fields", []):
            all_field_keys.add(field.get("key", ""))

    return {
        "profile_type": "duckdb",
        "upload_id": int(upload_id),
        "duckdb_row_index": int(row_index),
        "staging_id": staging_id,
        "citizen_id": citizen_id,
        "sections": sections,
        "source_links": [],
        "linked_departments": [record.get("department_name")] if record.get("department_name") else [],
        "source_count": 1,
        "staging_row_count": 1 if staging_id else 0,
        "duckdb_row_count": 1,
        "total_field_count": total_fields,
        "all_field_keys": sorted(k for k in all_field_keys if k),
    }


def build_person_360_profile(db: Session, citizen: Citizen) -> Dict[str, Any]:
    """Assemble grouped dynamic sections for one citizen."""
    sources = (
        db.query(PersonSource)
        .filter(PersonSource.citizen_id == int(citizen.id))
        .order_by(PersonSource.linked_at.desc())
        .all()
    )
    upload_ids = sorted({int(s.upload_batch_id) for s in sources if s.upload_batch_id})

    sections: List[Dict[str, Any]] = [_citizen_registry_section(citizen)]

    staging_rows = _fetch_linked_staging_rows(db, citizen.id, citizen)
    grouped_staging: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for row in staging_rows:
        section = _staging_to_section(row)
        key = _section_key(
            section.get("source_name") or "",
            section.get("department_name") or "",
            section.get("upload_batch_id"),
        )
        if key not in grouped_staging:
            grouped_staging[key] = section
        else:
            existing = grouped_staging[key]
            seen = {f"{f['key']}:{f['value']}".lower() for f in existing["fields"]}
            for field in section["fields"]:
                dedupe = f"{field['key']}:{field['value']}".lower()
                if dedupe not in seen:
                    existing["fields"].append(field)
                    seen.add(dedupe)
            existing["field_count"] = len(existing["fields"])

    sections.extend(grouped_staging.values())

    duckdb_records = _fetch_duckdb_rows(citizen, upload_ids)
    for idx, record in enumerate(duckdb_records):
        sections.append(_duckdb_row_to_section(record, index=idx))

    all_field_keys: Set[str] = set()
    total_fields = 0
    for section in sections:
        total_fields += section.get("field_count", 0)
        for field in section.get("fields", []):
            all_field_keys.add(field.get("key", ""))

    departments = sorted(
        {s.department_name for s in sources if s.department_name}
        | {sec.get("department_name") for sec in sections if sec.get("department_name")}
    )

    return {
        "sections": sections,
        "source_links": [
            {
                "id": s.id,
                "staging_id": s.staging_id,
                "upload_batch_id": s.upload_batch_id,
                "source_name": s.source_name,
                "department_name": s.department_name,
                "confidence_score": s.confidence_score,
                "linked_at": s.linked_at.isoformat() if s.linked_at else None,
            }
            for s in sources
        ],
        "linked_departments": departments,
        "source_count": len(sources),
        "staging_row_count": len(staging_rows),
        "duckdb_row_count": len(duckdb_records),
        "total_field_count": total_fields,
        "all_field_keys": sorted(k for k in all_field_keys if k),
    }


def mask_profile_360_fields(profile_360: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive values inside dynamic profile sections."""
    from app.services.masking_service import mask_mobile, mask_sensitive_text

    sensitive_keys = {
        "mobile",
        "aadhaar",
        "aadhar",
        "pan",
        "account_no",
        "aadhaar_token",
        "pan_token",
    }
    for section in profile_360.get("sections", []):
        for field in section.get("fields", []):
            key = (field.get("key") or "").lower()
            if key == "mobile":
                field["value"] = mask_mobile(field.get("value"))
            elif key in sensitive_keys:
                field["value"] = mask_sensitive_text(field.get("value"))
    return profile_360
