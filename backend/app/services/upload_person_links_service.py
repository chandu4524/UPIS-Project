import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.models.citizen import Citizen
from app.models.match_candidate import MatchCandidate
from app.models.person_source import PersonSource
from app.models.person_staging import PersonStaging
from app.models.upload import Upload

logger = get_logger("gpip.upload_person_links")


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


SENSITIVE_KEYS = {
    "aadhaar",
    "aadhaar_no",
    "aadhaar_number",
    "pan",
    "pan_no",
    "pan_number",
    "account_no",
    "account_number",
}


def _paginate(page: int, page_size: int) -> Tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    return page, page_size


def _mask_mobile(value: Any) -> str:
    s = "" if value is None else str(value).strip()
    if not s:
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def _safe_json_loads(value: Optional[str]) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _mask_json(payload: Any) -> Any:
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            lk = str(k).strip().lower()
            if lk in SENSITIVE_KEYS:
                out[k] = "***"
                continue
            if lk in {"mobile", "phone", "phone_number", "mobile_no", "mobile_number", "contact"}:
                out[k] = _mask_mobile(v)
                continue
            out[k] = _mask_json(v)
        return out
    if isinstance(payload, list):
        return [_mask_json(x) for x in payload]
    return payload


def _staging_to_public(s: PersonStaging) -> dict:
    raw = _mask_json(_safe_json_loads(s.raw_json))
    norm = _mask_json(_safe_json_loads(s.normalized_json))
    errs = _safe_json_loads(s.validation_errors) if s.validation_errors else []
    if not isinstance(errs, list):
        errs = []
    return {
        "id": s.id,
        "row_number": s.row_number,
        "confidence_level": s.confidence_level,
        "extraction_status": s.extraction_status,
        "matching_key": s.matching_key,
        "normalized_name": s.normalized_name,
        "mobile_hash": s.mobile_hash,
        "source_name": s.source_name,
        "department_name": s.department_name,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "raw_json": raw,
        "normalized_json": norm,
        "validation_errors": errs,
    }


def _citizen_public(c: Citizen) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "mobile": _mask_mobile(c.mobile),
        "district": c.district,
        "village": c.village,
        "dob": c.dob,
    }


def get_upload_person_links(
    db: Session,
    upload_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page, page_size = _paginate(page, page_size)

    upload = db.query(Upload).filter(Upload.id == int(upload_id)).first()
    if not upload:
        raise http_error(404, "Upload not found")

    base = db.query(PersonStaging).filter(PersonStaging.upload_batch_id == int(upload_id))
    total = base.count()
    staged_rows = (
        base.order_by(desc(PersonStaging.row_number), desc(PersonStaging.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    staging_ids = [s.id for s in staged_rows]
    candidates = (
        db.query(MatchCandidate)
        .filter(MatchCandidate.staging_id.in_(staging_ids))
        .order_by(desc(MatchCandidate.confidence_score), desc(MatchCandidate.id))
        .all()
        if staging_ids
        else []
    )

    sources = (
        db.query(PersonSource)
        .filter(PersonSource.upload_batch_id == int(upload_id))
        .order_by(desc(PersonSource.id))
        .all()
    )

    citizen_ids = sorted({c.citizen_id for c in sources if c.citizen_id} | {c.citizen_id for c in candidates if c.citizen_id})
    citizens = (
        db.query(Citizen).filter(Citizen.id.in_(citizen_ids)).all()
        if citizen_ids
        else []
    )
    citizen_map = {c.id: _citizen_public(c) for c in citizens}

    candidate_by_staging: Dict[int, List[dict]] = {}
    for c in candidates:
        reasons = _safe_json_loads(c.match_reasons)
        if not isinstance(reasons, list):
            reasons = []
        candidate_by_staging.setdefault(int(c.staging_id), []).append(
            {
                "id": c.id,
                "citizen_id": c.citizen_id,
                "matched_person_key": c.matched_person_key,
                "confidence_score": c.confidence_score,
                "match_category": c.match_category,
                "match_reasons": reasons,
                "review_status": c.review_status,
                "candidate_citizen": citizen_map.get(c.citizen_id) if c.citizen_id else None,
            }
        )

    sources_by_staging: Dict[int, List[dict]] = {}
    for s in sources:
        if not s.staging_id:
            continue
        sources_by_staging.setdefault(int(s.staging_id), []).append(
            {
                "id": s.id,
                "citizen_id": s.citizen_id,
                "upload_batch_id": s.upload_batch_id,
                "source_name": s.source_name,
                "department_name": s.department_name,
                "confidence_score": s.confidence_score,
                "linked_at": s.linked_at.isoformat() if s.linked_at else None,
            }
        )

    items = []
    for s in staged_rows:
        items.append(
            {
                "staging_row": _staging_to_public(s),
                "source_links": sources_by_staging.get(int(s.id), []),
                "candidates": candidate_by_staging.get(int(s.id), []),
            }
        )

    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "upload_info": {
            "id": upload.id,
            "filename": upload.filename,
            "uploaded_rows": upload.uploaded_rows,
            "uploaded_at": upload.uploaded_at.isoformat() if upload.uploaded_at else None,
        },
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

