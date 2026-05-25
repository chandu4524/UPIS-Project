import math
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

DEFAULT_PAGE_SIZE = 15
MAX_PAGE_SIZE = 100

ACTION_LOGIN = "LOGIN"
ACTION_UPLOAD_FILE = "UPLOAD_FILE"
ACTION_VIEW_PROFILE = "VIEW_PROFILE"
ACTION_OPEN_RELATIONSHIP_GRAPH = "OPEN_RELATIONSHIP_GRAPH"
ACTION_CITIZEN_SEARCH = "CITIZEN_SEARCH"
ACTION_INTELLIGENCE_SEARCH = "INTELLIGENCE_SEARCH"
ACTION_VIEW_SENSITIVE_FIELDS = "VIEW_SENSITIVE_FIELDS"
ACTION_CREATE_USER = "CREATE_USER"
ACTION_UPDATE_USER = "UPDATE_USER"
ACTION_RESET_PASSWORD = "RESET_PASSWORD"
ACTION_DISABLE_USER = "DISABLE_USER"


def log_action(
    db: Session,
    username: str,
    action_type: str,
    entity_type: str,
    entity_id: Optional[str] = None,
) -> None:
    """Persist an audit entry without interrupting the main request flow."""
    try:
        db.add(
            AuditLog(
                username=username,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def audit_log_to_dict(entry: AuditLog) -> dict:
    return {
        "id": entry.id,
        "username": entry.username,
        "action_type": entry.action_type,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def list_audit_logs_paginated(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    query = db.query(AuditLog)
    total = query.count()

    entries = (
        query.order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0

    return {
        "items": [audit_log_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
