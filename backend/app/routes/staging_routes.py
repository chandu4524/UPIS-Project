from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_UPLOAD_READ
from app.services.staging_history_service import (
    get_error_summary,
    get_upload_summary,
    list_error_rows,
    list_partial_rows,
    list_staging_rows,
)
from app.services.upload_person_links_service import get_upload_person_links
from app.utils.dependencies import get_db

router = APIRouter(tags=["Upload staging"])


@router.get("/uploads/{upload_id}/staging")
def staging_rows(
    upload_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    confidence: Optional[str] = Query(None),
    extraction_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    result = list_staging_rows(
        db,
        upload_id,
        page=page,
        page_size=page_size,
        confidence=confidence,
        extraction_status=extraction_status,
    )
    return {
        "success": True,
        "message": "Staging rows fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/uploads/{upload_id}/summary")
def staging_summary(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    summary = get_upload_summary(db, upload_id)
    return {
        "success": True,
        "message": "Upload staging summary fetched successfully",
        "logged_in_user": current_user.username,
        **summary,
    }


@router.get("/uploads/{upload_id}/errors")
def staging_errors(
    upload_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    confidence: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    result = list_error_rows(
        db,
        upload_id,
        page=page,
        page_size=page_size,
        confidence=confidence,
    )
    return {
        "success": True,
        "message": "Rejected rows fetched successfully",
        "logged_in_user": current_user.username,
        "error_summary": get_error_summary(db, upload_id),
        **result,
    }


@router.get("/uploads/{upload_id}/partials")
def staging_partials(
    upload_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    confidence: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    result = list_partial_rows(
        db,
        upload_id,
        page=page,
        page_size=page_size,
        confidence=confidence,
    )
    return {
        "success": True,
        "message": "Partial rows fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/uploads/{upload_id}/person-links")
def upload_person_links(
    upload_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    result = get_upload_person_links(db, upload_id, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Upload person links fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }

