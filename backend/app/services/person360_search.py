"""360 intelligence search — universal field scan with tiered ranking."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from rapidfuzz import fuzz
from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from app.models.citizen import Citizen
from app.models.person_source import PersonSource
from app.models.person_staging import PersonStaging
from app.services.citizen_service import mobile_lookup_key
from app.services.header_canonicalization import normalize_header
from app.core.logging_config import get_logger
from app.services.data_scope_service import get_dataset_scope, summarize_result_sources
from app.services.intelligence_search_service import (
    MIN_RELEVANCE_SCORE,
    _build_suggestions,
    _normalize_query,
    _score_citizen,
)

logger = get_logger("gpip.intelligence_search")

# Scan full staging / DuckDB when dataset size is below this threshold (no latest-batch filter).
FULL_DATASET_SCAN_THRESHOLD = 10000

PRIORITY_EXACT_FIELD = 1
PRIORITY_EXACT_MOBILE = 2
PRIORITY_FUZZY = 3

MATCH_BADGE_EXACT = "EXACT MATCH"
MATCH_BADGE_FUZZY = "FUZZY MATCH"

MOBILE_DIGIT_LEN = (10, 12)

SKIP_STAGING_ATTRS = frozenset(
    {
        "id",
        "raw_json",
        "normalized_json",
        "validation_errors",
        "created_at",
        "mobile_hash",
    }
)

SKIP_DUCKDB_META = frozenset({"upload_id", "source_file", "uploaded_at"})

IDENTIFIER_QUERY_RE = re.compile(
    r"^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z0-9][a-zA-Z0-9\-_/\.]{2,}$|"
    r"^[a-zA-Z]{2,}[-_][a-zA-Z0-9]{2,}$|"
    r"^[a-zA-Z]{2,}\d{2,}[a-zA-Z0-9\-]*$"
)


def _normalize_text_for_match(value: Any) -> str:
    """Collapse whitespace and lowercase for reliable exact text comparison."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("nan", "none"):
        return ""
    return " ".join(text.split()).lower()


def _significant_tokens(query: str, *, min_len: int = 3) -> List[str]:
    q = _normalize_text_for_match(query)
    if not q:
        return []
    tokens = [t for t in q.split() if len(t) >= min_len]
    if not tokens and q:
        return [q]
    return tokens


def _is_text_field_query(query: str) -> bool:
    """Plain text lookup (not identifier / mobile / key=value)."""
    q = query.strip()
    if not q or len(q) < 2:
        return False
    if _parse_kv_query(q):
        return False
    if _is_mobile_digit_query(q):
        return False
    if _is_identifier_query(q):
        return False
    return bool(re.search(r"[a-zA-Z]", q))


def _normalize_name_key(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).strip().lower().split())


def _compact_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _humanize_field(key: str) -> str:
    if not key:
        return "Field"
    return str(key).replace("_", " ").strip().title()


def _parse_kv_query(query: str) -> Optional[Tuple[str, str]]:
    if "=" not in query:
        return None
    key_part, val_part = query.split("=", 1)
    key_part = key_part.strip()
    val_part = val_part.strip()
    if key_part and val_part:
        return normalize_header(key_part) or key_part, val_part
    return None


def _value_exact_match(query: str, value: Any) -> bool:
    """Exact match: case-insensitive, trimmed, whitespace-normalized."""
    if value is None:
        return False
    text = _normalize_text_for_match(value)
    q = _normalize_text_for_match(query)
    if not text or not q:
        return False
    if text == q:
        return True
    return _compact_alnum(text) == _compact_alnum(q)


def _value_contains_query(query: str, value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    q = query.strip()
    if len(q) < 2 or not text:
        return False
    tl = text.lower()
    ql = q.lower()
    if ql in tl:
        return True
    # Avoid matching single digits / short tokens inside long queries (e.g. "2" in SBIN0001234).
    if len(tl) >= 4 and tl in ql:
        return True
    return False


def _is_mobile_digit_query(query: str) -> bool:
    digits = re.sub(r"\D", "", query)
    if not digits:
        return False
    if re.search(r"[a-zA-Z]", query):
        return False
    return len(digits) in range(MOBILE_DIGIT_LEN[0], MOBILE_DIGIT_LEN[1] + 1)


def _is_identifier_query(query: str) -> bool:
    q = query.strip()
    if not q or len(q) < 3:
        return False
    if _parse_kv_query(q):
        return False
    if _is_mobile_digit_query(q):
        return False
    if IDENTIFIER_QUERY_RE.match(q.replace(" ", "")):
        return True
    if re.search(r"[a-zA-Z]", q) and re.search(r"\d", q):
        return True
    if len(q) >= 5 and q.replace(" ", "").replace("-", "").isalnum() and re.search(r"\d", q):
        return True
    return False


def _safe_json_loads(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _iter_dynamic_staging_fields(
    row: PersonStaging,
    raw: Dict[str, Any],
    normalized: Dict[str, Any],
) -> Iterator[Tuple[str, str]]:
    """Yield every searchable value — all ORM columns + every JSON key (no hardcoded list)."""
    mapper = inspect(PersonStaging)
    for column in mapper.columns:
        key = column.key
        if key in SKIP_STAGING_ATTRS:
            continue
        val = getattr(row, key, None)
        if val is not None and str(val).strip() and str(val).lower() not in ("nan", "none"):
            yield key, str(val).strip()

    for source_dict in (normalized, raw):
        for json_key, val in source_dict.items():
            if val is None:
                continue
            text = str(val).strip()
            if not text or text.lower() in ("nan", "none"):
                continue
            canonical = normalize_header(str(json_key)) or str(json_key)
            yield canonical, text
            if canonical != str(json_key):
                yield str(json_key), text


def _iter_duckdb_record_fields(record: Dict[str, Any]) -> Iterator[Tuple[str, str]]:
    for key, val in record.items():
        if key in SKIP_DUCKDB_META:
            continue
        if val is None:
            continue
        text = str(val).strip()
        if not text or text.lower() in ("nan", "none"):
            continue
        canonical = normalize_header(str(key)) or str(key)
        yield canonical, text


def _score_field_match(
    query: str,
    field_key: str,
    field_value: str,
    *,
    identifier_mode: bool,
    exact_only: bool = False,
) -> Optional[Tuple[float, int, str]]:
    """
    Return (score, match_priority, match_kind) or None.
    match_kind: exact | contains | fuzzy
    """
    q = query.strip()
    if not q or not field_value:
        return None

    kv = _parse_kv_query(q)
    if kv:
        exp_key, exp_val = kv
        key_ok = normalize_header(field_key) == exp_key or field_key.lower() == exp_key.lower()
        if key_ok and _value_exact_match(exp_val, field_value):
            return 100.0, PRIORITY_EXACT_FIELD, "exact"
        if not exact_only and key_ok and _value_contains_query(exp_val, field_value):
            return 98.0, PRIORITY_EXACT_FIELD, "contains"
        return None

    if exact_only:
        if field_key == "mobile" and not _value_exact_match(q, field_value):
            return None
        if _value_exact_match(q, field_value):
            return 100.0, PRIORITY_EXACT_FIELD, "exact"
        return None

    if field_key == "mobile" and identifier_mode:
        if not _value_exact_match(q, field_value):
            return None

    if _value_exact_match(q, field_value):
        return 100.0, PRIORITY_EXACT_FIELD, "exact"

    if len(q) >= 2 and _value_contains_query(q, field_value):
        return 98.0, PRIORITY_EXACT_FIELD, "contains"

    if len(q) >= 3 and _value_contains_query(field_value, q):
        return 96.0, PRIORITY_EXACT_FIELD, "contains"

    if identifier_mode:
        return None

    if field_key == "mobile" and re.search(r"\d", q) and not re.search(r"[a-zA-Z]", q):
        digits_q = re.sub(r"\D", "", q)
        digits_v = re.sub(r"\D", "", field_value)
        if digits_q and len(digits_q) >= 4 and digits_q in digits_v and digits_q != digits_v:
            return None

    q_lower = q.lower()
    tl = field_value.lower()
    if q_lower in tl:
        return 88.0, PRIORITY_FUZZY, "fuzzy"
    score = float(
        max(
            fuzz.partial_ratio(q_lower, tl),
            fuzz.WRatio(q_lower, tl),
        )
    )
    if score >= MIN_RELEVANCE_SCORE:
        return score, PRIORITY_FUZZY, "fuzzy"
    return None


def _citizen_id_for_staging(db: Session, staging_id: int) -> Optional[int]:
    link = (
        db.query(PersonSource)
        .filter(PersonSource.staging_id == int(staging_id))
        .order_by(PersonSource.id.desc())
        .first()
    )
    return int(link.citizen_id) if link and link.citizen_id else None


def _source_label(row: PersonStaging) -> str:
    dept = (row.department_name or "").strip()
    src = (row.source_name or "").strip()
    if dept and src and dept.upper() not in src.upper():
        return f"{dept} · {src}"
    return dept or src or "Upload source"


def _build_staging_result(
    db: Session,
    row: PersonStaging,
    *,
    score: float,
    match_priority: int,
    matched_fields: List[str],
    match_field: str,
    match_value: str,
    match_kind: str,
) -> dict:
    cid = _citizen_id_for_staging(db, row.id)
    normalized = _safe_json_loads(row.normalized_json)
    raw = _safe_json_loads(row.raw_json)
    is_exact_tier = match_kind == "exact" and float(score) >= 100.0

    return {
        "id": cid or row.id,
        "citizen_id": cid,
        "staging_id": row.id,
        "full_name": row.full_name or normalized.get("full_name") or raw.get("full_name"),
        "mobile": row.mobile or normalized.get("mobile") or raw.get("mobile"),
        "district": row.district or normalized.get("district"),
        "village": row.village or normalized.get("village"),
        "dob": row.dob or normalized.get("dob"),
        "father_name": row.father_name or normalized.get("father_name"),
        "source_name": row.source_name,
        "department_name": row.department_name,
        "source_label": _source_label(row),
        "source_id": match_value if match_kind == "exact" else None,
        "upload_batch_id": row.upload_batch_id,
        "relevance_score": round(score, 2),
        "match_priority": match_priority,
        "match_badge": MATCH_BADGE_EXACT if is_exact_tier else MATCH_BADGE_FUZZY,
        "match_field": match_field,
        "match_field_label": _humanize_field(match_field),
        "match_value": match_value,
        "match_kind": match_kind,
        "matched_fields": matched_fields,
        "match_type": "staging",
        "result_source": "staging",
        "highlights": {},
    }


def _staging_candidate_query(db: Session, query: str, limit: int, *, broad: bool = False):
    q = query.strip()
    if not q:
        return []

    kv = _parse_kv_query(q)
    prefilter = kv[1] if kv else q
    like = f"%{prefilter}%"
    filters = [
        PersonStaging.raw_json.ilike(like),
        PersonStaging.normalized_json.ilike(like),
    ]

    mapper = inspect(PersonStaging)
    for column in mapper.columns:
        key = column.key
        if key in SKIP_STAGING_ATTRS:
            continue
        col_type = str(column.type).lower()
        if "string" in col_type or "text" in col_type or "varchar" in col_type:
            filters.append(getattr(PersonStaging, key).ilike(like))

    if broad or " " in q:
        for token in _significant_tokens(q):
            token_like = f"%{token}%"
            filters.append(PersonStaging.raw_json.ilike(token_like))
            filters.append(PersonStaging.normalized_json.ilike(token_like))

    total_staging = db.query(PersonStaging).count()
    if total_staging <= FULL_DATASET_SCAN_THRESHOLD and (broad or _is_text_field_query(q)):
        return (
            db.query(PersonStaging)
            .filter(or_(*filters))
            .order_by(PersonStaging.id)
            .all()
        )

    row_cap = max(limit * 80, 800) if broad or _is_text_field_query(q) else max(limit * 40, 400)
    return (
        db.query(PersonStaging)
        .filter(or_(*filters))
        .order_by(PersonStaging.id)
        .limit(row_cap)
        .all()
    )


def _resolve_staging_for_record(
    db: Session,
    *,
    upload_batch_id: Any,
    full_name: Any,
    match_value: str,
) -> Tuple[Optional[int], Optional[int]]:
    """Map a DuckDB row back to person_staging + citizen when possible."""
    if not upload_batch_id:
        return None, None

    q = db.query(PersonStaging).filter(
        PersonStaging.upload_batch_id == int(upload_batch_id)
    )
    if full_name and str(full_name).strip():
        q = q.filter(PersonStaging.full_name.ilike(str(full_name).strip()))

    for row in q.order_by(PersonStaging.id.desc()).limit(20).all():
        raw = _safe_json_loads(row.raw_json)
        normalized = _safe_json_loads(row.normalized_json)
        for _, text in _iter_dynamic_staging_fields(row, raw, normalized):
            if _value_exact_match(match_value, text):
                return row.id, _citizen_id_for_staging(db, row.id)
    return None, None


def _collect_staging_field_matches(
    db: Session,
    row: PersonStaging,
    query: str,
    *,
    identifier_mode: bool,
    exact_only: bool,
) -> Optional[dict]:
    raw = _safe_json_loads(row.raw_json)
    normalized = _safe_json_loads(row.normalized_json)

    best_score = 0.0
    best_priority = PRIORITY_FUZZY
    best_kind = ""
    matched_fields: List[str] = []
    match_field = ""
    match_value = ""

    for field_key, text in _iter_dynamic_staging_fields(row, raw, normalized):
        scored = _score_field_match(
            query,
            field_key,
            text,
            identifier_mode=identifier_mode,
            exact_only=exact_only,
        )
        if not scored:
            continue
        score, priority, kind = scored
        matched_fields.append(field_key)
        if score > best_score or (score == best_score and priority < best_priority):
            best_score = score
            best_priority = priority
            best_kind = kind
            match_field = field_key
            match_value = text

    if not matched_fields:
        return None
    if exact_only and best_kind != "exact":
        return None
    if not exact_only and best_score < MIN_RELEVANCE_SCORE:
        return None

    return _build_staging_result(
        db,
        row,
        score=best_score,
        match_priority=best_priority,
        matched_fields=matched_fields,
        match_field=match_field,
        match_value=match_value,
        match_kind=best_kind,
    )


def _search_staging_exact_text(
    db: Session,
    query: str,
    limit: int,
    seen_staging: Set[int],
) -> List[dict]:
    """Tier 1: exact text match on every uploaded field before any fuzzy search."""
    results: List[dict] = []
    for row in _staging_candidate_query(db, query, limit, broad=True):
        if row.id in seen_staging:
            continue
        item = _collect_staging_field_matches(
            db,
            row,
            query,
            identifier_mode=False,
            exact_only=True,
        )
        if not item:
            continue
        seen_staging.add(row.id)
        results.append(item)

    if not results and _is_text_field_query(query):
        total_staging = db.query(PersonStaging).count()
        fallback_rows = (
            db.query(PersonStaging).order_by(PersonStaging.id).all()
            if total_staging <= FULL_DATASET_SCAN_THRESHOLD
            else db.query(PersonStaging).order_by(PersonStaging.id).limit(2000).all()
        )
        for row in fallback_rows:
            if row.id in seen_staging:
                continue
            item = _collect_staging_field_matches(
                db,
                row,
                query,
                identifier_mode=False,
                exact_only=True,
            )
            if not item:
                continue
            seen_staging.add(row.id)
            results.append(item)
            if len(results) >= limit:
                break

    results.sort(
        key=lambda r: (
            r.get("match_priority", PRIORITY_FUZZY),
            -float(r.get("relevance_score") or 0),
        )
    )
    return results[:limit]


def _search_staging_universal(
    db: Session,
    query: str,
    limit: int,
    *,
    identifier_mode: bool,
    seen_staging: Set[int],
    exact_only: bool = False,
) -> List[dict]:
    """Scan ALL dynamic fields on staging rows; rank exact field hits first."""
    results: List[dict] = []
    for row in _staging_candidate_query(db, query, limit, broad=exact_only or _is_text_field_query(query)):
        if row.id in seen_staging:
            continue
        item = _collect_staging_field_matches(
            db,
            row,
            query,
            identifier_mode=identifier_mode,
            exact_only=exact_only,
        )
        if not item:
            continue
        seen_staging.add(row.id)
        results.append(item)

    results.sort(
        key=lambda r: (
            r.get("match_priority", PRIORITY_FUZZY),
            -float(r.get("relevance_score") or 0),
        )
    )
    return results[:limit]


def _search_duckdb_universal(
    query: str,
    limit: int,
    db: Optional[Session] = None,
    *,
    identifier_mode: bool,
    exact_only: bool = False,
) -> List[dict]:
    try:
        from app.services.duckdb_service import UPLOADED_DATA_TABLE, execute_query, table_exists
    except Exception:
        return []

    try:
        if not table_exists(UPLOADED_DATA_TABLE):
            return []
    except Exception:
        return []

    q = query.strip().lower()
    try:
        df = execute_query(f"SELECT * FROM {UPLOADED_DATA_TABLE}")
    except Exception:
        return []

    if df is None or df.empty:
        return []

    kv_prefilter = _parse_kv_query(query)
    tokens = _significant_tokens(query) if not kv_prefilter else []
    results: List[dict] = []
    for idx, record in enumerate(df.to_dict(orient="records")):
        if not kv_prefilter:
            row_blob = " ".join(str(v).lower() for v in record.values() if v is not None)
            blob_hit = (
                q in row_blob
                or _compact_alnum(q) in _compact_alnum(row_blob)
                or any(token in row_blob for token in tokens)
            )
            if not blob_hit:
                continue

        best_score = 0.0
        best_priority = PRIORITY_FUZZY
        best_kind = ""
        matched_fields: List[str] = []
        match_field = ""
        match_value = ""

        for field_key, text in _iter_duckdb_record_fields(record):
            scored = _score_field_match(
                query,
                field_key,
                text,
                identifier_mode=identifier_mode,
                exact_only=exact_only,
            )
            if not scored:
                continue
            score, priority, kind = scored
            matched_fields.append(field_key)
            if score > best_score or (score == best_score and priority < best_priority):
                best_score = score
                best_priority = priority
                best_kind = kind
                match_field = field_key
                match_value = text

        if not matched_fields:
            continue
        if exact_only and best_kind != "exact":
            continue

        staging_id = None
        citizen_id = None
        if db is not None:
            staging_id, citizen_id = _resolve_staging_for_record(
                db,
                upload_batch_id=record.get("upload_id"),
                full_name=record.get("full_name"),
                match_value=match_value,
            )

        is_exact_tier = best_kind == "exact" and float(best_score) >= 100.0
        upload_id_val = record.get("upload_id")
        results.append(
            {
                "id": citizen_id or staging_id or int(upload_id_val or 0) * 10000 + idx,
                "citizen_id": citizen_id,
                "staging_id": staging_id,
                "duckdb_row_index": idx,
                "upload_id": upload_id_val,
                "full_name": record.get("full_name"),
                "mobile": record.get("mobile"),
                "district": record.get("district"),
                "village": record.get("village"),
                "dob": record.get("dob"),
                "father_name": record.get("father_name"),
                "source_name": record.get("source_file"),
                "department_name": record.get("department_name"),
                "source_label": record.get("department_name") or record.get("source_file") or "DuckDB upload",
                "source_id": match_value if best_kind == "exact" else None,
                "upload_batch_id": record.get("upload_id"),
                "relevance_score": round(best_score, 2),
                "match_priority": best_priority,
                "match_badge": MATCH_BADGE_EXACT if is_exact_tier else MATCH_BADGE_FUZZY,
                "match_field": match_field,
                "match_field_label": _humanize_field(match_field),
                "match_value": match_value,
                "match_kind": best_kind,
                "matched_fields": matched_fields,
                "match_type": "duckdb",
                "result_source": "duckdb",
                "highlights": {},
            }
        )
        if len(results) >= limit:
            break

    results.sort(
        key=lambda r: (
            r.get("match_priority", PRIORITY_FUZZY),
            -float(r.get("relevance_score") or 0),
        )
    )
    return results[:limit]


def _search_exact_mobile(
    db: Session,
    query: str,
    limit: int,
    seen_citizen: Set[int],
    seen_staging: Set[int],
) -> List[dict]:
    mobile_key = mobile_lookup_key(query)
    if not mobile_key:
        return []

    results: List[dict] = []

    for citizen in db.query(Citizen).filter(Citizen.mobile == mobile_key).all():
        if citizen.id in seen_citizen:
            continue
        seen_citizen.add(citizen.id)
        results.append(
            {
                "id": citizen.id,
                "citizen_id": citizen.id,
                "staging_id": None,
                "full_name": citizen.full_name,
                "mobile": citizen.mobile,
                "district": citizen.district,
                "village": citizen.village,
                "dob": citizen.dob,
                "father_name": getattr(citizen, "father_name", None),
                "source_name": None,
                "department_name": None,
                "source_label": "Citizen registry",
                "source_id": None,
                "upload_batch_id": None,
                "relevance_score": 100.0,
                "match_priority": PRIORITY_EXACT_MOBILE,
                "match_badge": MATCH_BADGE_EXACT,
                "matched_fields": ["mobile"],
                "match_field": "mobile",
                "match_field_label": "Mobile",
                "match_value": mobile_key,
                "match_kind": "exact",
                "match_type": "citizen",
                "result_source": "citizen",
                "highlights": {},
            }
        )

    for row in db.query(PersonStaging).filter(PersonStaging.mobile == mobile_key).limit(limit * 2).all():
        if row.id in seen_staging:
            continue
        seen_staging.add(row.id)
        item = _build_staging_result(
            db,
            row,
            score=100.0,
            match_priority=PRIORITY_EXACT_MOBILE,
            matched_fields=["mobile"],
            match_field="mobile",
            match_value=mobile_key,
            match_kind="exact",
        )
        if item.get("citizen_id"):
            seen_citizen.add(int(item["citizen_id"]))
        results.append(item)

    return results[:limit]


def _search_citizens_fuzzy(
    db: Session,
    query: str,
    limit: int,
    seen_citizen: Set[int],
    *,
    identifier_mode: bool,
) -> List[dict]:
    if identifier_mode:
        return []

    scored: List[dict] = []
    q_compact = _compact_alnum(query)

    for citizen in db.query(Citizen).all():
        if citizen.id in seen_citizen:
            continue

        if re.search(r"\d", query) and citizen.mobile:
            digits_q = re.sub(r"\D", "", query)
            digits_m = re.sub(r"\D", "", str(citizen.mobile))
            if (
                digits_q
                and len(digits_q) >= 4
                and digits_q in digits_m
                and digits_q != digits_m
                and not _value_exact_match(query, citizen.mobile)
            ):
                continue

        row = _score_citizen(citizen, query)
        if not row:
            continue

        if row.get("matched_fields") == ["mobile"] and not _value_exact_match(query, citizen.mobile):
            if q_compact and q_compact in _compact_alnum(str(citizen.mobile or "")):
                continue

        seen_citizen.add(citizen.id)
        row["citizen_id"] = citizen.id
        row["staging_id"] = None
        row["match_type"] = "citizen"
        row["result_source"] = "citizen"
        row["match_priority"] = PRIORITY_FUZZY
        row["match_badge"] = MATCH_BADGE_FUZZY
        row["match_kind"] = "fuzzy"
        row["source_label"] = "Citizen registry"
        row["source_id"] = None
        if row.get("match_field"):
            row["match_field_label"] = _humanize_field(row["match_field"])
        scored.append(row)

    scored.sort(key=lambda r: (-r["relevance_score"], (r.get("full_name") or "").lower()))
    return scored[:limit]


def _detect_ambiguous_groups(results: List[dict]) -> List[dict]:
    by_name: Dict[str, List[dict]] = defaultdict(list)
    for row in results:
        if row.get("match_priority", PRIORITY_FUZZY) != PRIORITY_FUZZY:
            continue
        cid = row.get("citizen_id") or row.get("id")
        if not cid:
            continue
        name_key = _normalize_name_key(row.get("full_name"))
        if not name_key:
            continue
        by_name[name_key].append(row)

    ambiguous: List[dict] = []
    for name_key, group in by_name.items():
        if len(group) < 2:
            continue
        mobiles = {mobile_lookup_key(r.get("mobile")) or "" for r in group}
        ids = {r.get("citizen_id") or r.get("id") for r in group}
        if len(mobiles) > 1 or len(ids) > 1:
            ambiguous.append(
                {
                    "normalized_name": name_key,
                    "display_name": group[0].get("full_name") or name_key,
                    "message": "Multiple matching profiles found",
                    "candidates": [
                        {
                            "citizen_id": r.get("citizen_id") or r.get("id"),
                            "full_name": r.get("full_name"),
                            "mobile": r.get("mobile"),
                            "source_id": r.get("source_id") or r.get("match_value"),
                            "district": r.get("district"),
                            "village": r.get("village"),
                            "relevance_score": r.get("relevance_score"),
                            "matched_fields": r.get("matched_fields", []),
                            "match_badge": r.get("match_badge"),
                            "staging_id": r.get("staging_id"),
                            "match_field_label": r.get("match_field_label"),
                        }
                        for r in group
                    ],
                }
            )
    return ambiguous


def _merge_ranked(*groups: List[dict]) -> List[dict]:
    combined: List[dict] = []
    for group in groups:
        combined.extend(group)
    return _dedupe_results(
        sorted(
            combined,
            key=lambda r: (
                r.get("match_priority", PRIORITY_FUZZY),
                -float(r.get("relevance_score") or 0),
                (r.get("full_name") or "").lower(),
            ),
        )
    )


def _dedupe_results(results: List[dict]) -> List[dict]:
    """Prefer staging/citizen rows over duplicate DuckDB hits for the same match."""
    type_rank = {"staging": 0, "citizen": 1, "duckdb": 2}
    ordered = sorted(
        results,
        key=lambda r: (
            type_rank.get(r.get("match_type"), 9),
            r.get("match_priority", PRIORITY_FUZZY),
            -float(r.get("relevance_score") or 0),
        ),
    )
    seen: Set[Tuple[Any, ...]] = set()
    out: List[dict] = []
    for row in ordered:
        key = (
            (row.get("full_name") or "").lower(),
            (row.get("match_field") or "").lower(),
            (row.get("match_value") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return sorted(
        out,
        key=lambda r: (
            r.get("match_priority", PRIORITY_FUZZY),
            -float(r.get("relevance_score") or 0),
            (r.get("full_name") or "").lower(),
        ),
    )


def intelligence_search_360(
    db: Session,
    query: str,
    limit: int = 25,
) -> dict:
    q = _normalize_query(query)
    if not q:
        return {
            "query": "",
            "results": [],
            "staging_results": [],
            "ambiguous_groups": [],
            "suggestions": [],
            "total": 0,
            "identifier_query": False,
            "search_mode": "empty",
        }

    identifier_mode = _is_identifier_query(q)
    seen_citizen: Set[int] = set()
    seen_staging: Set[int] = set()

    tier1_exact_text = _search_staging_exact_text(db, q, limit, seen_staging)
    for item in tier1_exact_text:
        if item.get("citizen_id"):
            seen_citizen.add(int(item["citizen_id"]))

    tier1_identifier: List[dict] = []
    if identifier_mode:
        tier1_identifier = _search_staging_universal(
            db,
            q,
            limit,
            identifier_mode=True,
            seen_staging=seen_staging,
            exact_only=True,
        )
        for item in tier1_identifier:
            if item.get("citizen_id"):
                seen_citizen.add(int(item["citizen_id"]))

    tier1_duckdb = _search_duckdb_universal(
        q,
        limit,
        db,
        identifier_mode=identifier_mode,
        exact_only=True,
    )
    tier1 = _merge_ranked(tier1_exact_text, tier1_identifier, tier1_duckdb)[:limit]

    tier2 = _search_exact_mobile(db, q, limit, seen_citizen, seen_staging)

    has_exact_text_hit = any(
        r.get("match_kind") == "exact" and float(r.get("relevance_score") or 0) >= 100.0
        for r in tier1
    )

    if identifier_mode or has_exact_text_hit:
        ranked = _merge_ranked(tier1, tier2)[:limit]
        search_mode = "exact_text" if has_exact_text_hit and not identifier_mode else "exact_only"
    else:
        tier3_staging = _search_staging_universal(
            db,
            q,
            limit,
            identifier_mode=False,
            seen_staging=seen_staging,
            exact_only=False,
        )
        tier3_duckdb = _search_duckdb_universal(
            q,
            limit,
            db,
            identifier_mode=False,
            exact_only=False,
        )
        tier3_citizens = _search_citizens_fuzzy(
            db, q, limit, seen_citizen, identifier_mode=False
        )
        ranked = _merge_ranked(tier1, tier2, tier3_staging, tier3_duckdb, tier3_citizens)[:limit]
        search_mode = "universal"

    ambiguous_groups = _detect_ambiguous_groups(ranked)

    ambiguous_ids: Set[int] = set()
    for group in ambiguous_groups:
        for candidate in group.get("candidates", []):
            cid = candidate.get("citizen_id")
            if cid:
                ambiguous_ids.add(int(cid))

    flat_results = [
        r for r in ranked if not r.get("citizen_id") or int(r["citizen_id"]) not in ambiguous_ids
    ]

    suggestions = _build_suggestions(flat_results[:50], q)

    scope = get_dataset_scope(db)
    result_sources = summarize_result_sources(flat_results)
    diagnostics = {
        "search_scope": {
            "citizens": scope["citizens"],
            "staging": scope["person_staging"],
            "duckdb": scope["uploaded_data"],
        },
        "result_sources": result_sources,
    }
    logger.info(
        "Intelligence search query=%r mode=%s scope citizens=%s staging=%s duckdb=%s results=%s sources=%s",
        q,
        search_mode,
        scope["citizens"],
        scope["person_staging"],
        scope["uploaded_data"],
        len(flat_results),
        result_sources,
    )

    return {
        "query": q,
        "results": flat_results,
        "staging_results": [],
        "ambiguous_groups": ambiguous_groups,
        "suggestions": suggestions,
        "total": len(ranked),
        "identifier_query": identifier_mode,
        "search_mode": search_mode,
        "diagnostics": diagnostics,
    }
