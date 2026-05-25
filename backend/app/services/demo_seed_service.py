"""Ensure minimum demo data exists for dashboards, reports, and assistant (additive only)."""

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.audit_log import AuditLog
from app.models.citizen import Citizen
from app.models.ocr_document import OcrDocument
from app.models.upload import Upload
from app.services.entity_resolution_service import sync_review_queue

logger = get_logger("gpip.demo_seed")

MIN_CITIZENS = 8
MIN_UPLOADS = 2
MIN_AUDIT_LOGS = 3
MIN_OCR_DOCS = 1

DEMO_CITIZENS: List[Dict[str, str]] = [
    {
        "full_name": "Chandu Kumar",
        "mobile": "9876500001",
        "district": "Visakhapatnam",
        "village": "MVP Colony",
        "dob": "15-03-1990",
    },
    {
        "full_name": "Chandu Reddy",
        "mobile": "9876500002",
        "district": "Visakhapatnam",
        "village": "Gajuwaka",
        "dob": "15-03-1990",
    },
    {
        "full_name": "Priya Sharma",
        "mobile": "9876500003",
        "district": "Hyderabad",
        "village": "Banjara Hills",
        "dob": "22-07-1992",
    },
    {
        "full_name": "Ravi Teja",
        "mobile": "9876500004",
        "district": "Guntur",
        "village": "Arundalpet",
        "dob": "10-11-1988",
    },
    {
        "full_name": "Anitha Rao",
        "mobile": "9876500005",
        "district": "Vijayawada",
        "village": "One Town",
        "dob": "05-01-1995",
    },
    {
        "full_name": "Suresh Babu",
        "mobile": "9876500006",
        "district": "Visakhapatnam",
        "village": "Madhurawada",
        "dob": "18-09-1985",
    },
    {
        "full_name": "Lakshmi Devi",
        "mobile": "9876500007",
        "district": "Kurnool",
        "village": "Nandyal Road",
        "dob": "30-04-1991",
    },
    {
        "full_name": "Venkatesh Naidu",
        "mobile": "9876500008",
        "district": "Visakhapatnam",
        "village": "Anakapalle",
        "dob": "12-12-1987",
    },
]


def _existing_mobiles(db: Session) -> set:
    rows = db.query(Citizen.mobile).all()
    return {str(r[0]).strip() for r in rows if r[0]}


def ensure_demo_citizens(db: Session) -> int:
    existing = _existing_mobiles(db)
    added = 0
    for row in DEMO_CITIZENS:
        mobile = row["mobile"]
        if mobile in existing:
            continue
        db.add(
            Citizen(
                full_name=row["full_name"],
                mobile=mobile,
                district=row["district"],
                village=row["village"],
                dob=row["dob"],
            )
        )
        existing.add(mobile)
        added += 1
    if added:
        db.commit()
    return added


def ensure_demo_uploads(db: Session) -> int:
    count = db.query(Upload).count()
    if count >= MIN_UPLOADS:
        return 0
    now = datetime.utcnow()
    samples = [
        ("citizens_batch_01.csv", 120, now - timedelta(days=5)),
        ("village_registry_q2.csv", 85, now - timedelta(days=2)),
        ("district_update_may.csv", 45, now - timedelta(hours=6)),
    ]
    added = 0
    for filename, rows, uploaded_at in samples:
        if db.query(Upload).filter(Upload.filename == filename).first():
            continue
        db.add(
            Upload(
                filename=filename,
                uploaded_rows=rows,
                uploaded_at=uploaded_at,
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def ensure_demo_audit_logs(db: Session) -> int:
    count = db.query(AuditLog).count()
    if count >= MIN_AUDIT_LOGS:
        return 0
    samples = [
        ("officer", "LOGIN", "user", "officer"),
        ("officer", "UPLOAD_FILE", "upload", "citizens_batch_01.csv"),
        ("officer", "CITIZEN_SEARCH", "citizen", "page=1"),
        ("officer", "INTELLIGENCE_SEARCH", "intelligence_search", "Chandu"),
    ]
    added = 0
    for username, action, entity_type, entity_id in samples:
        exists = (
            db.query(AuditLog)
            .filter(
                AuditLog.action_type == action,
                AuditLog.entity_id == entity_id,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            AuditLog(
                username=username,
                action_type=action,
                entity_type=entity_type,
                entity_id=entity_id,
                created_at=datetime.utcnow() - timedelta(hours=added + 1),
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def ensure_demo_ocr_documents(db: Session) -> int:
    count = db.query(OcrDocument).count()
    if count >= MIN_OCR_DOCS:
        return 0
    if db.query(OcrDocument).filter(OcrDocument.filename == "demo_registry.pdf").first():
        return 0
    db.add(
        OcrDocument(
            filename="demo_registry.pdf",
            extracted_text="Demo OCR extract — Chandu Kumar, Visakhapatnam, MVP Colony.",
            confidence_score=88.5,
            created_at=datetime.utcnow() - timedelta(days=1),
        )
    )
    db.commit()
    return 1


def verify_and_seed_demo_data(db: Session) -> Dict[str, int]:
    """
    Top up demo records when counts are low. Does not alter schema or remove data.
    """
    citizen_count = db.query(Citizen).count()
    result = {
        "citizens_added": 0,
        "uploads_added": 0,
        "audit_logs_added": 0,
        "ocr_documents_added": 0,
        "reviews_synced": 0,
    }

    if citizen_count < MIN_CITIZENS:
        result["citizens_added"] = ensure_demo_citizens(db)

    result["uploads_added"] = ensure_demo_uploads(db)
    result["audit_logs_added"] = ensure_demo_audit_logs(db)
    result["ocr_documents_added"] = ensure_demo_ocr_documents(db)

    try:
        sync_review_queue(db)
        result["reviews_synced"] = 1
    except Exception as exc:
        logger.warning("Demo review queue sync skipped: %s", exc)

    total_added = sum(
        v for k, v in result.items() if k != "reviews_synced" and isinstance(v, int)
    )
    if total_added or result["reviews_synced"]:
        logger.info("Demo seed verification complete: %s", result)
    else:
        logger.info("Demo seed verification — data already sufficient")

    return result
