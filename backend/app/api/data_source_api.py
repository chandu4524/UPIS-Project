from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_TEMPLATE_WRITE, PERM_UPLOAD_READ, has_permission
from app.services.data_source_service import (
    create_data_source,
    data_source_to_dict,
    delete_data_source,
    get_data_source,
    list_data_sources,
    update_data_source,
)
from app.core.exceptions import http_error
from app.utils.dependencies import get_db

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


class DataSourceCreate(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=255)
    source_code: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None
    is_active: bool = True


class DataSourceUpdate(BaseModel):
    source_name: Optional[str] = Field(None, min_length=1, max_length=255)
    source_code: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def get_data_sources(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    can_manage = has_permission(current_user.role, PERM_TEMPLATE_WRITE)
    items = list_data_sources(
        db,
        active_only=active_only or not can_manage,
    )
    return {
        "success": True,
        "message": "Data sources fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
        "total": len(items),
    }


@router.post("")
def create_data_source_route(
    body: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    item = create_data_source(
        db,
        source_name=body.source_name,
        source_code=body.source_code,
        description=body.description,
        is_active=body.is_active,
    )
    return {
        "success": True,
        "message": "Data source created successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.put("/{source_id}")
def update_data_source_route(
    source_id: int,
    body: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    if (
        body.source_name is None
        and body.source_code is None
        and body.description is None
        and body.is_active is None
    ):
        raise http_error(400, "Provide at least one field to update")

    item = update_data_source(
        db,
        source_id,
        source_name=body.source_name,
        source_code=body.source_code,
        description=body.description,
        is_active=body.is_active,
    )
    return {
        "success": True,
        "message": "Data source updated successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.delete("/{source_id}")
def delete_data_source_route(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    existing = get_data_source(db, source_id)
    if not existing:
        raise http_error(404, "Data source not found")

    snapshot = data_source_to_dict(existing)
    delete_data_source(db, source_id)
    return {
        "success": True,
        "message": "Data source deleted successfully",
        "logged_in_user": current_user.username,
        "item": snapshot,
    }
