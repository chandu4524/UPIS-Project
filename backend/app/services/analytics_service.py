"""Intelligence analytics aggregates for the dashboard."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.citizen import Citizen
from app.models.entity_review import EntityReview
from app.models.ocr_document import OcrDocument
from app.models.upload import Upload
from app.services.entity_resolution_service import (
    CATEGORY_CONFIRMED,
    CATEGORY_MANUAL,
    CATEGORY_PROBABLE,
)

TOP_DISTRICTS_LIMIT = 10
UPLOAD_TREND_DAYS = 30
RECENT_ACTIONS_LIMIT = 8


def _district_analytics(db: Session) -> dict:
    rows = (
        db.query(Citizen.district, func.count(Citizen.id).label("count"))
        .filter(Citizen.district.isnot(None), Citizen.district != "")
        .group_by(Citizen.district)
        .order_by(desc("count"))
        .all()
    )

    distribution = [
        {"district": (district or "Unknown"), "count": int(count)}
        for district, count in rows
    ]
    top_districts = distribution[:TOP_DISTRICTS_LIMIT]
    total_with_district = sum(item["count"] for item in distribution)
    total_citizens = db.query(func.count(Citizen.id)).scalar() or 0

    return {
        "top_districts": top_districts,
        "distribution": distribution,
        "total_citizens": int(total_citizens),
        "citizens_with_district": int(total_with_district),
    }


def _upload_analytics(db: Session) -> dict:
    uploads = (
        db.query(Upload)
        .order_by(Upload.uploaded_at.asc())
        .all()
    )

    cutoff = datetime.utcnow() - timedelta(days=UPLOAD_TREND_DAYS)
    by_date: Dict[str, dict] = defaultdict(
        lambda: {"date": "", "uploads": 0, "imported_rows": 0}
    )

    for upload in uploads:
        if not upload.uploaded_at:
            continue
        day_key = upload.uploaded_at.strftime("%Y-%m-%d")
        entry = by_date[day_key]
        entry["date"] = day_key
        entry["uploads"] += 1
        entry["imported_rows"] += int(upload.uploaded_rows or 0)

    over_time = sorted(by_date.values(), key=lambda x: x["date"])
    if cutoff:
        over_time = [row for row in over_time if row["date"] >= cutoff.strftime("%Y-%m-%d")]

    total_uploads = db.query(func.count(Upload.id)).scalar() or 0
    total_imported_rows = (
        db.query(func.coalesce(func.sum(Upload.uploaded_rows), 0)).scalar() or 0
    )

    return {
        "over_time": over_time,
        "total_uploads": int(total_uploads),
        "total_imported_rows": int(total_imported_rows),
    }


def _entity_resolution_analytics(db: Session) -> dict:
    def count_category(category: str) -> int:
        return (
            db.query(func.count(EntityReview.id))
            .filter(EntityReview.category == category)
            .scalar()
            or 0
        )

    pending_manual = (
        db.query(func.count(EntityReview.id))
        .filter(
            EntityReview.category == CATEGORY_MANUAL,
            EntityReview.status == "pending",
        )
        .scalar()
        or 0
    )

    return {
        "confirmed_matches": int(count_category(CATEGORY_CONFIRMED)),
        "probable_matches": int(count_category(CATEGORY_PROBABLE)),
        "manual_review_count": int(count_category(CATEGORY_MANUAL)),
        "pending_manual_review": int(pending_manual),
        "total_reviews": int(db.query(func.count(EntityReview.id)).scalar() or 0),
    }


def _ocr_analytics(db: Session) -> dict:
    processed = db.query(func.count(OcrDocument.id)).scalar() or 0
    avg_confidence = (
        db.query(func.avg(OcrDocument.confidence_score)).scalar()
        if processed
        else None
    )

    return {
        "processed_documents": int(processed),
        "avg_confidence_score": round(float(avg_confidence), 2)
        if avg_confidence is not None
        else 0.0,
    }


def _audit_analytics(db: Session) -> dict:
    officer_rows = (
        db.query(AuditLog.username, func.count(AuditLog.id).label("action_count"))
        .group_by(AuditLog.username)
        .order_by(desc("action_count"))
        .limit(10)
        .all()
    )

    officer_activity = [
        {"username": username, "action_count": int(count)}
        for username, count in officer_rows
    ]

    total_actions = db.query(func.count(AuditLog.id)).scalar() or 0
    officer_count = db.query(func.count(func.distinct(AuditLog.username))).scalar() or 0

    recent_logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(RECENT_ACTIONS_LIMIT)
        .all()
    )

    recent_actions = [
        {
            "id": log.id,
            "username": log.username,
            "action_type": log.action_type,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in recent_logs
    ]

    return {
        "officer_activity_count": int(officer_count),
        "total_actions": int(total_actions),
        "officer_activity": officer_activity,
        "recent_actions": recent_actions,
    }


def get_dashboard_analytics(db: Session) -> dict:
    return {
        "district": _district_analytics(db),
        "uploads": _upload_analytics(db),
        "entity_resolution": _entity_resolution_analytics(db),
        "ocr": _ocr_analytics(db),
        "audit": _audit_analytics(db),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
