import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.models.person_staging import PersonStaging
from app.models.upload import Upload

logger = get_logger("gpip.staging_history")


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


def _mask_mobile(value: Any) -> str:
    s = "" if value is None else str(value).strip()
    if not s:
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def _mask_json_payload(payload: Any) -> Any:
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
            out[k] = _mask_json_payload(v)
        return out
    if isinstance(payload, list):
        return [_mask_json_payload(x) for x in payload]
    return payload


def _safe_json_loads(value: Optional[str]) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _row_to_dict(row: PersonStaging) -> dict:
    raw = _mask_json_payload(_safe_json_loads(row.raw_json))
    norm = _mask_json_payload(_safe_json_loads(row.normalized_json))
    errors = _safe_json_loads(row.validation_errors) if row.validation_errors else []
    if not isinstance(errors, list):
        errors = []
    return {
        "id": row.id,
        "row_number": row.row_number,
        "raw_json": raw,
        "normalized_json": norm,
        "confidence_level": row.confidence_level,
        "extraction_status": row.extraction_status,
        "validation_errors": errors,
        "matching_key": row.matching_key,
        "normalized_name": row.normalized_name,
        "mobile_hash": row.mobile_hash,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _paginate(page: int, page_size: int) -> Tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    return page, page_size


def list_staging_rows(
    db: Session,
    upload_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    confidence: Optional[str] = None,
    extraction_status: Optional[str] = None,
) -> dict:
    page, page_size = _paginate(page, page_size)

    query = db.query(PersonStaging).filter(PersonStaging.upload_batch_id == int(upload_id))
    if confidence:
        query = query.filter(PersonStaging.confidence_level == str(confidence).upper())
    if extraction_status:
        query = query.filter(PersonStaging.extraction_status == str(extraction_status).lower())

    total = query.count()
    items = (
        query.order_by(desc(PersonStaging.row_number), desc(PersonStaging.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [_row_to_dict(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _error_bucket(error_type: str) -> str:
    key = (error_type or "").upper()
    if "MISSING" in key:
        return "missing_fields"
    if "DUPLICATE_MOBILE" in key or "DUPLICATE" in key:
        return "duplicate_mobile"
    if "INVALID_DOB" in key or "DOB" in key:
        return "invalid_dob"
    if "EMPTY_ROW" in key or "EMPTY" in key:
        return "empty_row"
    return "other"


def get_error_summary(db: Session, upload_id: int) -> dict:
    rows = (
        db.query(PersonStaging.validation_errors)
        .filter(PersonStaging.upload_batch_id == int(upload_id))
        .all()
    )
    summary = {
        "missing_fields": 0,
        "duplicate_mobile": 0,
        "invalid_dob": 0,
        "empty_row": 0,
        "other": 0,
    }
    for (err_str,) in rows:
        errors = _safe_json_loads(err_str)
        if not isinstance(errors, list):
            continue
        for e in errors:
            et = ""
            if isinstance(e, dict):
                et = e.get("error_type") or e.get("type") or ""
            elif isinstance(e, str):
                et = e
            bucket = _error_bucket(et)
            summary[bucket] = summary.get(bucket, 0) + 1
    return summary


def get_upload_summary(db: Session, upload_id: int) -> dict:
    upload = db.query(Upload).filter(Upload.id == int(upload_id)).first()
    if not upload:
        raise http_error(404, "Upload not found")

    base = db.query(PersonStaging).filter(PersonStaging.upload_batch_id == int(upload_id))
    total_rows = base.count()
    staged_rows = total_rows
    partial_rows = base.filter(PersonStaging.extraction_status == "partial").count()
    rejected_rows = base.filter(PersonStaging.extraction_status == "rejected").count()

    confidence_summary = {
        "HIGH": base.filter(PersonStaging.confidence_level == "HIGH").count(),
        "MEDIUM": base.filter(PersonStaging.confidence_level == "MEDIUM").count(),
        "LOW": base.filter(PersonStaging.confidence_level == "LOW").count(),
    }

    error_summary = get_error_summary(db, upload_id)

    return {
        "total_rows": total_rows,
        "staged_rows": staged_rows,
        "imported_rows": int(upload.uploaded_rows or 0),
        "partial_rows": partial_rows,
        "rejected_rows": rejected_rows,
        "confidence_summary": confidence_summary,
        "error_summary": error_summary,
        "upload_info": {
            "id": upload.id,
            "filename": upload.filename,
            "uploaded_rows": upload.uploaded_rows,
            "uploaded_at": upload.uploaded_at.isoformat() if upload.uploaded_at else None,
        },
    }


def list_partial_rows(
    db: Session,
    upload_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    confidence: Optional[str] = None,
) -> dict:
    return list_staging_rows(
        db,
        upload_id,
        page=page,
        page_size=page_size,
        confidence=confidence,
        extraction_status="partial",
    )


def list_error_rows(
    db: Session,
    upload_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    confidence: Optional[str] = None,
) -> dict:
    return list_staging_rows(
        db,
        upload_id,
        page=page,
        page_size=page_size,
        confidence=confidence,
        extraction_status="rejected",
    )

