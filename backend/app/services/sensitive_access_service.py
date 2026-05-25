"""Apply masking and audit logging for sensitive field access."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.services.audit_service import ACTION_VIEW_SENSITIVE_FIELDS, log_action
from app.services.masking_service import (
    apply_citizen_list_masking,
    apply_citizen_masking,
    can_view_sensitive_fields,
    mask_relationship_graph,
    sensitive_access_meta,
)


def _log_sensitive_view(
    db: Session,
    username: str,
    entity_type: str,
    entity_id: str,
) -> None:
    log_action(
        db,
        username=username,
        action_type=ACTION_VIEW_SENSITIVE_FIELDS,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def prepare_citizen_record(
    db: Session,
    citizen_data: dict,
    current_user: CurrentUser,
    *,
    log_context: Optional[str] = None,
) -> dict:
    """Mask or pass through a single citizen record; audit unmasked views."""
    can_view = can_view_sensitive_fields(current_user.role)
    if can_view:
        if log_context:
            _log_sensitive_view(
                db,
                current_user.username,
                "citizen",
                log_context,
            )
        return citizen_data
    return apply_citizen_masking(citizen_data)


def prepare_citizen_list_response(
    db: Session,
    items: List[dict],
    current_user: CurrentUser,
    *,
    log_list: bool = False,
    list_context: str = "list",
) -> Tuple[List[dict], Dict[str, bool]]:
    can_view = can_view_sensitive_fields(current_user.role)
    meta = sensitive_access_meta(current_user.role)
    if can_view:
        if log_list and items:
            _log_sensitive_view(
                db,
                current_user.username,
                "citizen",
                list_context,
            )
        return items, meta
    return apply_citizen_list_masking(items), meta


def prepare_relationship_graph(
    db: Session,
    graph: Optional[dict],
    current_user: CurrentUser,
    citizen_id: int,
) -> Tuple[Optional[dict], Dict[str, bool]]:
    can_view = can_view_sensitive_fields(current_user.role)
    meta = sensitive_access_meta(current_user.role)
    if can_view:
        _log_sensitive_view(
            db,
            current_user.username,
            "citizen",
            f"relationships:{citizen_id}",
        )
        return graph, meta
    return mask_relationship_graph(graph), meta
