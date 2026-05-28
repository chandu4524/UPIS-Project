import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.models.citizen import Citizen
from app.models.match_candidate import MatchCandidate
from app.models.person_staging import PersonStaging
from app.services.audit_service import log_action
from app.models.person_source import PersonSource
from app.services.relationship_extraction_service import (
    extract_relationships_from_staging,
    upsert_relationships,
)

logger = get_logger("gpip.manual_review_v2")


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _safe_json_loads(value: Optional[str]) -> Any:
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


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


def _citizen_preview(c: Optional[Citizen]) -> Optional[dict]:
    if not c:
        return None
    return {
        "id": c.id,
        "full_name": c.full_name,
        "mobile": _mask_mobile(c.mobile),
        "district": c.district,
        "village": c.village,
        "dob": c.dob,
    }


def _staging_preview(s: Optional[PersonStaging]) -> Optional[dict]:
    if not s:
        return None
    return {
        "id": s.id,
        "row_number": s.row_number,
        "full_name": s.full_name,
        "normalized_name": s.normalized_name,
        "mobile": _mask_mobile(s.mobile),
        "village": s.village,
        "district": s.district,
        "dob": s.dob,
        "confidence_level": s.confidence_level,
        "extraction_status": s.extraction_status,
        "validation_errors": _safe_json_loads(s.validation_errors),
        "matching_key": s.matching_key,
        "mobile_hash": s.mobile_hash,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "upload_batch_id": s.upload_batch_id,
    }


def _candidate_to_dict(db: Session, c: MatchCandidate) -> dict:
    staging = db.query(PersonStaging).filter(PersonStaging.id == c.staging_id).first()
    citizen = (
        db.query(Citizen).filter(Citizen.id == c.citizen_id).first()
        if c.citizen_id
        else None
    )
    reasons = _safe_json_loads(c.match_reasons)
    if not isinstance(reasons, list):
        reasons = []
    return {
        "id": c.id,
        "staging_id": c.staging_id,
        "citizen_id": c.citizen_id,
        "matched_person_key": c.matched_person_key,
        "confidence_score": c.confidence_score,
        "match_category": c.match_category,
        "match_reasons": reasons,
        "review_status": c.review_status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "staging_row": _staging_preview(staging),
        "candidate_citizen": _citizen_preview(citizen),
    }


def list_pending(
    db: Session,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    category: Optional[str] = None,
) -> dict:
    page, page_size = _paginate(page, page_size)
    q = db.query(MatchCandidate).filter(MatchCandidate.review_status == "pending")
    if category:
        q = q.filter(MatchCandidate.match_category == str(category).lower())
    total = q.count()
    rows = (
        q.order_by(desc(MatchCandidate.confidence_score), desc(MatchCandidate.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [_candidate_to_dict(db, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_candidate(db: Session, candidate_id: int) -> dict:
    c = db.query(MatchCandidate).filter(MatchCandidate.id == int(candidate_id)).first()
    if not c:
        raise http_error(404, "Review candidate not found")
    return _candidate_to_dict(db, c)


def approve_candidate(db: Session, candidate_id: int, *, username: str) -> dict:
    c = db.query(MatchCandidate).filter(MatchCandidate.id == int(candidate_id)).first()
    if not c:
        raise http_error(404, "Review candidate not found")
    if c.review_status != "pending":
        raise http_error(400, "Candidate is already resolved")
    c.review_status = "approved"
    c.updated_at = datetime.utcnow()
    db.commit()
    log_action(db, username=username, action_type="REVIEW_APPROVE", entity_type="match_candidate", entity_id=str(c.id))

    # Source linking (safe, additive) when candidate is approved and points to a citizen.
    if c.citizen_id:
        staging = db.query(PersonStaging).filter(PersonStaging.id == c.staging_id).first()
        if staging:
            db.add(
                PersonSource(
                    citizen_id=int(c.citizen_id),
                    staging_id=int(staging.id),
                    upload_batch_id=int(staging.upload_batch_id or 0) or None,
                    source_name=staging.source_name,
                    department_name=staging.department_name,
                    confidence_score=int(c.confidence_score or 0),
                )
            )
            db.commit()
            # relationship extraction (safe additive)
            rels = extract_relationships_from_staging(
                staging,
                citizen_id=int(c.citizen_id),
                confidence_score=int(c.confidence_score or 0),
                source_name=staging.source_name,
            )
            upsert_relationships(db, rels)

    return _candidate_to_dict(db, c)


def reject_candidate(db: Session, candidate_id: int, *, username: str) -> dict:
    c = db.query(MatchCandidate).filter(MatchCandidate.id == int(candidate_id)).first()
    if not c:
        raise http_error(404, "Review candidate not found")
    if c.review_status != "pending":
        raise http_error(400, "Candidate is already resolved")
    c.review_status = "rejected"
    c.updated_at = datetime.utcnow()
    db.commit()
    log_action(db, username=username, action_type="REVIEW_REJECT", entity_type="match_candidate", entity_id=str(c.id))
    return _candidate_to_dict(db, c)


def merge_candidate(db: Session, candidate_id: int, *, username: str) -> dict:
    """
    Safe merge preparation only:
    - mark as merged
    - write audit entry
    - do NOT modify/delete citizens or staging rows
    """
    c = db.query(MatchCandidate).filter(MatchCandidate.id == int(candidate_id)).first()
    if not c:
        raise http_error(404, "Review candidate not found")
    if c.review_status != "pending":
        raise http_error(400, "Candidate is already resolved")
    c.review_status = "merged"
    c.updated_at = datetime.utcnow()
    db.commit()
    log_action(db, username=username, action_type="REVIEW_MERGE_PREP", entity_type="match_candidate", entity_id=str(c.id))
    return {
        "item": _candidate_to_dict(db, c),
        "message": "Merge prepared (no data was overwritten).",
    }

