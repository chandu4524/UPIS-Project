from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_TEMPLATE_WRITE
from app.core.exceptions import http_error
from app.services.template_mapping_service import (
    get_template_mapping_by_id,
    list_template_mappings,
    save_template_mapping,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Template Mapping"])


class TemplateMappingSaveRequest(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=255)
    mapping: Dict[str, Any]


@router.post("/template-mapping/save")
def save_template(
    body: TemplateMappingSaveRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    record = save_template_mapping(db, body.template_name, body.mapping)
    return {
        "success": True,
        "message": "Template mapping saved successfully",
        "logged_in_user": current_user.username,
        "template": record,
    }


@router.get("/template-mapping")
def get_templates(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    templates = list_template_mappings(db)
    return {
        "success": True,
        "message": "Template mappings fetched successfully",
        "logged_in_user": current_user.username,
        "templates": templates,
    }


@router.get("/template-mapping/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_TEMPLATE_WRITE)),
):
    record = get_template_mapping_by_id(db, template_id)
    if not record:
        raise http_error(404, "Template mapping not found")
    return {
        "success": True,
        "message": "Template mapping fetched successfully",
        "logged_in_user": current_user.username,
        "template": record,
    }
