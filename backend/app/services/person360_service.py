import json
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.models.citizen import Citizen
from app.models.person_relationship import PersonRelationship
from app.models.person_source import PersonSource

logger = get_logger("gpip.person360")


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


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


def _citizen_to_public_dict(c: Citizen) -> dict:
    return {
        "id": c.id,
        "full_name": c.full_name,
        "mobile": _mask_mobile(c.mobile),
        "district": c.district,
        "village": c.village,
        "dob": c.dob,
        "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
    }


def _profile_confidence(source_rows: List[PersonSource]) -> str:
    if not source_rows:
        return "LOW"
    best = max(int(s.confidence_score or 0) for s in source_rows)
    if best >= 90:
        return "HIGH"
    if best >= 75:
        return "MEDIUM"
    return "LOW"


def search_persons(
    db: Session,
    *,
    name: Optional[str] = None,
    mobile: Optional[str] = None,
    district: Optional[str] = None,
    village: Optional[str] = None,
    department: Optional[str] = None,
    confidence: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page, page_size = _paginate(page, page_size)
    q = db.query(Citizen)
    if name:
        q = q.filter(Citizen.full_name.ilike(f"%{name.strip()}%"))
    if mobile:
        q = q.filter(Citizen.mobile.ilike(f"%{mobile.strip()}%"))
    if district:
        q = q.filter(Citizen.district.ilike(f"%{district.strip()}%"))
    if village:
        q = q.filter(Citizen.village.ilike(f"%{village.strip()}%"))

    # Optional filters based on sources
    if department or confidence:
        source_q = (
            db.query(
                PersonSource.citizen_id.label("citizen_id"),
                func.count(PersonSource.id).label("source_count"),
                func.max(PersonSource.confidence_score).label("max_confidence"),
            )
            .group_by(PersonSource.citizen_id)
        )
        if department:
            source_q = source_q.filter(PersonSource.department_name.ilike(f"%{department.strip()}%"))
        source_sq = source_q.subquery()
        q = q.join(source_sq, source_sq.c.citizen_id == Citizen.id)
        if confidence:
            key = str(confidence).strip().upper()
            if key == "HIGH":
                q = q.filter(source_sq.c.max_confidence >= 90)
            elif key == "MEDIUM":
                q = q.filter(source_sq.c.max_confidence >= 75, source_sq.c.max_confidence < 90)
            elif key == "LOW":
                q = q.filter(source_sq.c.max_confidence < 75)

    total = q.count()
    rows = (
        q.order_by(desc(Citizen.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0

    # Attach source_count / confidence / linked_departments without changing citizen model
    ids = [r.id for r in rows]
    source_counts: Dict[int, int] = {}
    max_conf: Dict[int, int] = {}
    departments_by_id: Dict[int, List[str]] = {}
    if ids:
        agg = (
            db.query(
                PersonSource.citizen_id,
                func.count(PersonSource.id),
                func.max(PersonSource.confidence_score),
            )
            .filter(PersonSource.citizen_id.in_(ids))
            .group_by(PersonSource.citizen_id)
            .all()
        )
        for cid, cnt, mx in agg:
            source_counts[int(cid)] = int(cnt or 0)
            max_conf[int(cid)] = int(mx or 0)
        dep = (
            db.query(PersonSource.citizen_id, PersonSource.department_name)
            .filter(PersonSource.citizen_id.in_(ids))
            .all()
        )
        for cid, dname in dep:
            if not dname:
                continue
            departments_by_id.setdefault(int(cid), set()).add(str(dname))
        departments_by_id = {k: sorted(list(v)) for k, v in departments_by_id.items()}

    def _confidence_label(mx: int) -> str:
        if mx >= 90:
            return "HIGH"
        if mx >= 75:
            return "MEDIUM"
        return "LOW"

    return {
        "items": [
            {
                **_citizen_to_public_dict(r),
                "source_count": source_counts.get(r.id, 0),
                "confidence": _confidence_label(max_conf.get(r.id, 0)),
                "linked_departments": departments_by_id.get(r.id, []),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_search_summary(db: Session) -> dict:
    total_persons = db.query(Citizen).count()
    linked_persons = db.query(PersonSource.citizen_id).distinct().count()

    dept_rows = (
        db.query(PersonSource.department_name, func.count(PersonSource.id))
        .filter(PersonSource.department_name.isnot(None))
        .group_by(PersonSource.department_name)
        .all()
    )
    department_distribution = {str(name): int(cnt) for name, cnt in dept_rows if name}

    # confidence distribution based on max confidence_score per citizen
    max_rows = (
        db.query(PersonSource.citizen_id, func.max(PersonSource.confidence_score))
        .group_by(PersonSource.citizen_id)
        .all()
    )
    conf = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for _, mx in max_rows:
        mxv = int(mx or 0)
        if mxv >= 90:
            conf["HIGH"] += 1
        elif mxv >= 75:
            conf["MEDIUM"] += 1
        else:
            conf["LOW"] += 1

    rel_rows = (
        db.query(PersonRelationship.relationship_type, func.count(PersonRelationship.id))
        .group_by(PersonRelationship.relationship_type)
        .all()
    )
    relationship_counts = {str(rt): int(cnt) for rt, cnt in rel_rows if rt}

    return {
        "total_persons": total_persons,
        "linked_persons": linked_persons,
        "department_distribution": department_distribution,
        "confidence_distribution": conf,
        "relationship_counts": relationship_counts,
    }


def get_person_profile(db: Session, citizen_id: int) -> dict:
    citizen = db.query(Citizen).filter(Citizen.id == int(citizen_id)).first()
    if not citizen:
        raise http_error(404, "Person not found")

    sources = (
        db.query(PersonSource)
        .filter(PersonSource.citizen_id == int(citizen_id))
        .order_by(desc(PersonSource.linked_at), desc(PersonSource.id))
        .all()
    )
    departments = sorted({s.department_name for s in sources if s.department_name})
    profile_conf = _profile_confidence(sources)

    rels = (
        db.query(PersonRelationship)
        .filter(PersonRelationship.citizen_id == int(citizen_id))
        .all()
    )
    rel_summary = Counter([r.relationship_type for r in rels if r.relationship_type])

    return {
        "citizen": _citizen_to_public_dict(citizen),
        "profile_confidence": profile_conf,
        "source_count": len(sources),
        "linked_departments": departments,
        "relationship_summary": dict(rel_summary),
    }


def get_person_sources(
    db: Session,
    citizen_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page, page_size = _paginate(page, page_size)
    q = db.query(PersonSource).filter(PersonSource.citizen_id == int(citizen_id))
    total = q.count()
    rows = (
        q.order_by(desc(PersonSource.linked_at), desc(PersonSource.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [
            {
                "id": r.id,
                "citizen_id": r.citizen_id,
                "staging_id": r.staging_id,
                "upload_batch_id": r.upload_batch_id,
                "source_name": r.source_name,
                "department_name": r.department_name,
                "confidence_score": r.confidence_score,
                "linked_at": r.linked_at.isoformat() if r.linked_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_person_relationships(
    db: Session,
    citizen_id: int,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page, page_size = _paginate(page, page_size)
    q = db.query(PersonRelationship).filter(PersonRelationship.citizen_id == int(citizen_id))
    total = q.count()
    rows = (
        q.order_by(desc(PersonRelationship.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [
            {
                "id": r.id,
                "citizen_id": r.citizen_id,
                "related_entity_type": r.related_entity_type,
                "related_entity_value": r.related_entity_value,
                "relationship_type": r.relationship_type,
                "confidence_score": r.confidence_score,
                "source_name": r.source_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

