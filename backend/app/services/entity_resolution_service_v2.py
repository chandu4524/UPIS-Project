import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.citizen import Citizen
from app.models.match_candidate import MatchCandidate
from app.models.person_staging import PersonStaging
from app.services.normalization_service import normalize_name, normalize_phone
from app.models.person_source import PersonSource
from app.services.relationship_extraction_service import (
    extract_relationships_from_staging,
    upsert_relationships,
)

logger = get_logger("gpip.entity_resolution_v2")


CATEGORY_CONFIRMED = "confirmed"
CATEGORY_PROBABLE = "probable"
CATEGORY_MANUAL_REVIEW = "manual_review"
CATEGORY_NO_MATCH = "no_match"


STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_MERGED = "merged"


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


def score_to_category(score: int) -> str:
    if score >= 90:
        return CATEGORY_CONFIRMED
    if score >= 75:
        return CATEGORY_PROBABLE
    if score >= 55:
        return CATEGORY_MANUAL_REVIEW
    return CATEGORY_NO_MATCH


def calculate_match_score_staging_to_citizen(
    staging: PersonStaging,
    citizen: Citizen,
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    # Same Mobile = +60
    sm = _norm_phone(getattr(staging, "mobile", None))
    cm = _norm_phone(getattr(citizen, "mobile", None))
    if sm and cm and sm == cm:
        score += 60
        reasons.append("Same mobile number")

    # Same Name + DOB = +50
    sn = _norm_text(getattr(staging, "full_name", None) or getattr(staging, "normalized_name", None))
    cn = _norm_text(getattr(citizen, "full_name", None))
    sd = _norm_dob(getattr(staging, "dob", None))
    cd = _norm_dob(getattr(citizen, "dob", None))
    if sn and cn and sn == cn and sd and cd and sd == cd:
        score += 50
        reasons.append("Same name and date of birth")

    # Same Name + Father = +45 (citizens table may not have father_name; keep safe)
    sf = _norm_text(getattr(staging, "father_name", None))
    cf = _norm_text(getattr(citizen, "father_name", None))
    if sn and cn and sn == cn and sf and cf and sf == cf:
        score += 45
        reasons.append("Same name and father name")

    # Same Address + Mobile = +45 (approximate using village/district when present)
    sv = _norm_text(getattr(staging, "village", None))
    sdistrict = _norm_text(getattr(staging, "district", None))
    cv = _norm_text(getattr(citizen, "village", None))
    cdistrict = _norm_text(getattr(citizen, "district", None))
    if sm and cm and sm == cm and sv and cv and sv == cv and sdistrict == cdistrict:
        score += 45
        reasons.append("Same village/district and mobile")

    # Aadhaar / PAN rules cannot be applied against current citizens table (not stored there).
    return score, reasons


def calculate_match_score_staging_to_staging(
    a: PersonStaging,
    b: PersonStaging,
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    # Same Aadhaar token = +90
    aa = (getattr(a, "aadhaar_token", None) or "").strip()
    ba = (getattr(b, "aadhaar_token", None) or "").strip()
    if aa and ba and aa == ba:
        score += 90
        reasons.append("Same Aadhaar token")

    # Same PAN token = +85
    ap = (getattr(a, "pan_token", None) or "").strip()
    bp = (getattr(b, "pan_token", None) or "").strip()
    if ap and bp and ap == bp:
        score += 85
        reasons.append("Same PAN token")

    # Same Mobile = +60 (use mobile_hash if present, else normalized phone)
    ah = (getattr(a, "mobile_hash", None) or "").strip()
    bh = (getattr(b, "mobile_hash", None) or "").strip()
    if ah and bh and ah == bh:
        score += 60
        reasons.append("Same mobile hash")
    else:
        am = _norm_phone(getattr(a, "mobile", None))
        bm = _norm_phone(getattr(b, "mobile", None))
        if am and bm and am == bm:
            score += 60
            reasons.append("Same mobile number")

    # Same Name + DOB = +50
    an = _norm_text(getattr(a, "normalized_name", None) or getattr(a, "full_name", None))
    bn = _norm_text(getattr(b, "normalized_name", None) or getattr(b, "full_name", None))
    ad = _norm_dob(getattr(a, "dob", None))
    bd = _norm_dob(getattr(b, "dob", None))
    if an and bn and an == bn and ad and bd and ad == bd:
        score += 50
        reasons.append("Same name and date of birth")

    # Same Name + Father = +45
    af = _norm_text(getattr(a, "father_name", None))
    bf = _norm_text(getattr(b, "father_name", None))
    if an and bn and an == bn and af and bf and af == bf:
        score += 45
        reasons.append("Same name and father name")

    # Same Address + Mobile = +45 (village + district + mobile)
    av = _norm_text(getattr(a, "village", None))
    bv = _norm_text(getattr(b, "village", None))
    adist = _norm_text(getattr(a, "district", None))
    bdist = _norm_text(getattr(b, "district", None))
    am = _norm_phone(getattr(a, "mobile", None))
    bm = _norm_phone(getattr(b, "mobile", None))
    if am and bm and am == bm and av and bv and av == bv and adist and bdist and adist == bdist:
        score += 45
        reasons.append("Same address context and mobile")

    return score, reasons


def _candidate_exists(db: Session, staging_id: int, citizen_id: Optional[int]) -> bool:
    q = db.query(MatchCandidate).filter(MatchCandidate.staging_id == int(staging_id))
    if citizen_id is None:
        q = q.filter(MatchCandidate.citizen_id.is_(None))
    else:
        q = q.filter(MatchCandidate.citizen_id == int(citizen_id))
    return db.query(q.exists()).scalar() is True


def generate_candidates_for_upload(
    db: Session,
    upload_id: int,
    *,
    max_citizens_scan: int = 800,
    min_score_to_store: int = 55,
) -> Dict[str, Any]:
    """
    Generate MatchCandidate rows from PersonStaging for the given upload batch.
    Safe: does not merge or overwrite citizen data.
    """
    staged = (
        db.query(PersonStaging)
        .filter(PersonStaging.upload_batch_id == int(upload_id))
        .order_by(PersonStaging.id.asc())
        .all()
    )
    if not staged:
        return {"created": 0, "skipped": 0, "message": "No staged rows found"}

    citizens = db.query(Citizen).order_by(Citizen.id.desc()).limit(max_citizens_scan).all()

    created = 0
    skipped = 0
    now = datetime.utcnow()

    # staging-to-staging: only compare within the same upload batch (safe, bounded).
    # Store as a candidate with citizen_id=None and matched_person_key="staging:<other_id>".
    for i, a in enumerate(staged):
        for b in staged[i + 1 :]:
            score, reasons = calculate_match_score_staging_to_staging(a, b)
            if score < min_score_to_store:
                continue
            # avoid duplicates: one record per 'a' storing the best match only
            # (keeps candidate explosion under control)
            if _candidate_exists(db, a.id, None):
                continue
            db.add(
                MatchCandidate(
                    staging_id=a.id,
                    citizen_id=None,
                    matched_person_key=f"staging:{b.id}",
                    confidence_score=int(score),
                    match_category=score_to_category(score),
                    match_reasons=json.dumps(reasons),
                    review_status=STATUS_PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1

    for s in staged:
        best: Tuple[int, Optional[Citizen], List[str]] = (0, None, [])
        # Lightweight candidate search:
        # if mobile present, only compare against citizens with matching mobile digits (fast).
        sm = _norm_phone(getattr(s, "mobile", None))
        candidate_citizens = citizens
        if sm:
            candidate_citizens = [c for c in citizens if _norm_phone(getattr(c, "mobile", None)) == sm]

        for c in candidate_citizens:
            score, reasons = calculate_match_score_staging_to_citizen(s, c)
            if score > best[0]:
                best = (score, c, reasons)

        score = best[0]
        citizen = best[1]
        reasons = best[2]

        if score < min_score_to_store:
            # still store a no_match candidate if none exists yet
            if _candidate_exists(db, s.id, None):
                skipped += 1
                continue
            candidate = MatchCandidate(
                staging_id=s.id,
                citizen_id=None,
                matched_person_key=getattr(s, "matching_key", None),
                confidence_score=int(score),
                match_category=score_to_category(score),
                match_reasons=json.dumps(reasons),
                review_status=STATUS_PENDING,
                created_at=now,
                updated_at=now,
            )
            db.add(candidate)
            created += 1
            continue

        if citizen and _candidate_exists(db, s.id, citizen.id):
            skipped += 1
            continue

        candidate = MatchCandidate(
            staging_id=s.id,
            citizen_id=citizen.id if citizen else None,
            matched_person_key=getattr(s, "matching_key", None),
            confidence_score=int(score),
            match_category=score_to_category(score),
            match_reasons=json.dumps(reasons),
            review_status=STATUS_PENDING,
            created_at=now,
            updated_at=now,
        )
        db.add(candidate)
        created += 1

        # If it's a confirmed match, link source automatically (safe & additive).
        if citizen and score_to_category(score) == CATEGORY_CONFIRMED:
            db.add(
                PersonSource(
                    citizen_id=int(citizen.id),
                    staging_id=int(s.id),
                    upload_batch_id=int(s.upload_batch_id or 0) or None,
                    source_name=s.source_name,
                    department_name=s.department_name,
                    confidence_score=int(score),
                )
            )
            db.commit()
            rels = extract_relationships_from_staging(
                s,
                citizen_id=int(citizen.id),
                confidence_score=int(score),
                source_name=s.source_name,
            )
            upsert_relationships(db, rels)

    db.commit()
    logger.info("Generated match candidates for upload %s: created=%s skipped=%s", upload_id, created, skipped)
    return {"created": created, "skipped": skipped}

