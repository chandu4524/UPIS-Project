from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_CITIZENS_READ
from app.core.exceptions import http_error
from app.services.audit_service import (
    ACTION_CITIZEN_SEARCH,
    ACTION_OPEN_RELATIONSHIP_GRAPH,
    ACTION_VIEW_PROFILE,
    log_action,
)
from app.services.citizen_service import (
    build_citizen_relationship_graph,
    citizen_detail_dict,
    get_citizen_by_id,
    search_citizens_paginated,
)
from app.services.masking_service import sensitive_access_meta
from app.services.sensitive_access_service import (
    prepare_citizen_list_response,
    prepare_citizen_record,
    prepare_relationship_graph,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Citizens"])


@router.get("/citizens")
def get_citizens(
    name: Optional[str] = Query(None, description="Filter by full name"),
    mobile: Optional[str] = Query(None, description="Filter by mobile"),
    district: Optional[str] = Query(None, description="Filter by district"),
    village: Optional[str] = Query(None, description="Filter by village"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query(
        "full_name",
        regex="^(full_name|name|mobile|district)$",
    ),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_CITIZENS_READ)),
):
    result = search_citizens_paginated(
        db,
        name=name or "",
        mobile=mobile or "",
        district=district or "",
        village=village or "",
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if any(
        [
            (name or "").strip(),
            (mobile or "").strip(),
            (district or "").strip(),
            (village or "").strip(),
        ]
    ):
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_CITIZEN_SEARCH,
            entity_type="citizen",
            entity_id=f"page={page}",
        )
    items, access_meta = prepare_citizen_list_response(
        db,
        result.get("items", []),
        current_user,
        log_list=bool(result.get("items")),
        list_context=f"page={page}",
    )
    return {
        "success": True,
        "message": "Citizen records fetched successfully",
        "logged_in_user": current_user.username,
        **access_meta,
        **{**result, "items": items},
    }


@router.get("/citizens/{citizen_id}")
def get_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_CITIZENS_READ)),
):
    citizen = get_citizen_by_id(db, citizen_id)
    if not citizen:
        raise http_error(404, "Citizen not found")
    log_action(
        db,
        username=current_user.username,
        action_type=ACTION_VIEW_PROFILE,
        entity_type="citizen",
        entity_id=str(citizen_id),
    )
    citizen_data = prepare_citizen_record(
        db,
        citizen_detail_dict(citizen),
        current_user,
        log_context=str(citizen_id),
    )
    return {
        "success": True,
        "message": "Citizen profile fetched successfully",
        "logged_in_user": current_user.username,
        "citizen": citizen_data,
        **sensitive_access_meta(current_user.role),
    }


@router.get("/citizens/{citizen_id}/relationships")
def get_citizen_relationships(
    citizen_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_CITIZENS_READ)),
):
    graph = build_citizen_relationship_graph(db, citizen_id)
    if not graph:
        raise http_error(404, "Citizen not found")
    log_action(
        db,
        username=current_user.username,
        action_type=ACTION_OPEN_RELATIONSHIP_GRAPH,
        entity_type="citizen",
        entity_id=str(citizen_id),
    )
    graph_out, access_meta = prepare_relationship_graph(
        db, graph, current_user, citizen_id
    )
    return {
        "success": True,
        "message": "Relationship graph fetched successfully",
        "logged_in_user": current_user.username,
        "graph": graph_out,
        **access_meta,
    }
