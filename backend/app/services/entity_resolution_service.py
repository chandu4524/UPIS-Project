import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.models.citizen import Citizen
from app.models.entity_review import EntityReview
from app.services.citizen_service import citizen_to_dict
from app.services.normalization_service import normalize_name, normalize_phone

CATEGORY_CONFIRMED = "CONFIRMED_MATCH"
CATEGORY_PROBABLE = "PROBABLE_MATCH"
CATEGORY_MANUAL = "MANUAL_REVIEW"
CATEGORY_NO_MATCH = "NO_MATCH"

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_MERGED = "merged"

MAX_COMPARE_CITIZENS = 800


def _norm_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return normalize_name(str(value)).lower()


def _norm_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    return normalize_phone(str(value))


def _norm_dob(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip()


def _get_father_name(citizen: Citizen) -> str:
    return getattr(citizen, "father_name", None) or ""


def calculate_match_score(citizen_a: Citizen, citizen_b: Citizen) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    mobile_a = _norm_phone(citizen_a.mobile)
    mobile_b = _norm_phone(citizen_b.mobile)
    if mobile_a and mobile_b and mobile_a == mobile_b:
        score += 60
        reasons.append("Same mobile number")

    name_a = _norm_text(citizen_a.full_name)
    name_b = _norm_text(citizen_b.full_name)
    dob_a = _norm_dob(citizen_a.dob)
    dob_b = _norm_dob(citizen_b.dob)
    if name_a and name_b and name_a == name_b and dob_a and dob_b and dob_a == dob_b:
        score += 50
        reasons.append("Same name and date of birth")

    father_a = _norm_text(_get_father_name(citizen_a))
    father_b = _norm_text(_get_father_name(citizen_b))
    if name_a and name_b and name_a == name_b and father_a and father_b and father_a == father_b:
        score += 45
        reasons.append("Same name and father name")

    village_a = _norm_text(citizen_a.village)
    village_b = _norm_text(citizen_b.village)
    district_a = _norm_text(citizen_a.district)
    district_b = _norm_text(citizen_b.district)
    if village_a and village_b and village_a == village_b and district_a == district_b:
        if "Same village and district" not in reasons:
            reasons.append("Same village and district (context)")

    return score, reasons


def score_to_category(score: int) -> str:
    if score >= 90:
        return CATEGORY_CONFIRMED
    if score >= 75:
        return CATEGORY_PROBABLE
    if score >= 55:
        return CATEGORY_MANUAL
    return CATEGORY_NO_MATCH


def category_label(category: str) -> str:
    labels = {
        CATEGORY_CONFIRMED: "Confirmed Match",
        CATEGORY_PROBABLE: "Probable Match",
        CATEGORY_MANUAL: "Manual Review",
        CATEGORY_NO_MATCH: "No Match",
    }
    return labels.get(category, category)


def _pair_ids(a_id: int, b_id: int) -> Tuple[int, int]:
    return (min(a_id, b_id), max(a_id, b_id))


def _citizen_snapshot(citizen: Citizen) -> dict:
    data = citizen_to_dict(citizen)
    data["father_name"] = _get_father_name(citizen) or None
    return data


def _review_to_dict(review: EntityReview, db: Session) -> dict:
    citizen_a = db.query(Citizen).filter(Citizen.id == review.citizen_a_id).first()
    citizen_b = db.query(Citizen).filter(Citizen.id == review.citizen_b_id).first()
    try:
        reasons = json.loads(review.match_reasons or "[]")
    except json.JSONDecodeError:
        reasons = []
    return {
        "id": review.id,
        "citizen_a_id": review.citizen_a_id,
        "citizen_b_id": review.citizen_b_id,
        "person_a": _citizen_snapshot(citizen_a) if citizen_a else None,
        "person_b": _citizen_snapshot(citizen_b) if citizen_b else None,
        "match_score": review.match_score,
        "match_reasons": reasons,
        "match_reason": "; ".join(reasons),
        "category": review.category,
        "category_label": category_label(review.category),
        "status": review.status,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "resolved_at": review.resolved_at.isoformat() if review.resolved_at else None,
    }


def _load_resolved_pair_keys(db: Session) -> Set[Tuple[int, int]]:
    rows = (
        db.query(EntityReview)
        .filter(EntityReview.status != STATUS_PENDING)
        .all()
    )
    return {_pair_ids(r.citizen_a_id, r.citizen_b_id) for r in rows}


def sync_review_queue(db: Session) -> None:
    citizens = db.query(Citizen).order_by(Citizen.id).limit(MAX_COMPARE_CITIZENS).all()
    if len(citizens) < 2:
        return

    resolved_pairs = _load_resolved_pair_keys(db)
    pending_pairs = {
        _pair_ids(r.citizen_a_id, r.citizen_b_id)
        for r in db.query(EntityReview).filter(EntityReview.status == STATUS_PENDING).all()
    }

    for i, citizen_a in enumerate(citizens):
        for citizen_b in citizens[i + 1 :]:
            pair = _pair_ids(citizen_a.id, citizen_b.id)
            if pair in resolved_pairs or pair in pending_pairs:
                continue

            score, reasons = calculate_match_score(citizen_a, citizen_b)
            category = score_to_category(score)
            if score < 55:
                continue

            review = EntityReview(
                citizen_a_id=pair[0],
                citizen_b_id=pair[1],
                match_score=score,
                match_reasons=json.dumps(reasons),
                category=category,
                status=STATUS_PENDING,
            )
            db.add(review)
            pending_pairs.add(pair)

    db.commit()


def list_pending_reviews(db: Session) -> List[dict]:
    sync_review_queue(db)
    reviews = (
        db.query(EntityReview)
        .filter(EntityReview.status == STATUS_PENDING)
        .order_by(EntityReview.match_score.desc(), EntityReview.id.desc())
        .all()
    )
    return [_review_to_dict(r, db) for r in reviews]


def _get_review(db: Session, review_id: int) -> EntityReview:
    review = db.query(EntityReview).filter(EntityReview.id == review_id).first()
    if not review:
        raise http_error(404, "Review item not found")
    return review


def approve_review(db: Session, review_id: int) -> dict:
    review = _get_review(db, review_id)
    if review.status != STATUS_PENDING:
        raise http_error(400, "Review item is already resolved")
    review.status = STATUS_APPROVED
    review.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return _review_to_dict(review, db)


def reject_review(db: Session, review_id: int) -> dict:
    review = _get_review(db, review_id)
    if review.status != STATUS_PENDING:
        raise http_error(400, "Review item is already resolved")
    review.status = STATUS_REJECTED
    review.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return _review_to_dict(review, db)


def merge_review_profiles(db: Session, review_id: int) -> dict:
    review = _get_review(db, review_id)
    if review.status != STATUS_PENDING:
        raise http_error(400, "Review item is already resolved")

    keeper = db.query(Citizen).filter(Citizen.id == review.citizen_a_id).first()
    duplicate = db.query(Citizen).filter(Citizen.id == review.citizen_b_id).first()
    if not keeper or not duplicate:
        raise http_error(404, "One or both citizen records not found")

    for field in ("full_name", "mobile", "district", "village", "dob"):
        if not getattr(keeper, field, None) and getattr(duplicate, field, None):
            setattr(keeper, field, getattr(duplicate, field))

    db.delete(duplicate)
    review.status = STATUS_MERGED
    review.resolved_at = datetime.utcnow()

    db.query(EntityReview).filter(
        EntityReview.status == STATUS_PENDING,
        or_(
            EntityReview.citizen_a_id == duplicate.id,
            EntityReview.citizen_b_id == duplicate.id,
        ),
    ).delete(synchronize_session=False)

    db.commit()
    db.refresh(review)
    return {
        "review": _review_to_dict(review, db),
        "merged_into_id": keeper.id,
        "message": "Profiles merged successfully",
    }
