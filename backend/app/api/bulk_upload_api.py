from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_UPLOAD_READ, PERM_UPLOAD_WRITE
from app.core.exceptions import http_error
from app.services.audit_service import ACTION_UPLOAD_FILE, log_action
from app.services.bulk_upload_service import get_bulk_batch, list_bulk_batch_files, run_bulk_upload
from app.utils.dependencies import get_db

router = APIRouter(tags=["Bulk Upload"])


@router.post("/bulk-uploads")
def create_bulk_upload(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_WRITE)),
):
    """
    Bulk multi-file ingestion (CSV, XLSX, JSON, XML, PDF).
    Each file is processed independently; one failure does not stop others.
    """
    result = run_bulk_upload(db, files, created_by=current_user.username)
    if result.get("success") and result.get("batch"):
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_UPLOAD_FILE,
            entity_type="upload_batch",
            entity_id=str(result["batch"].get("id", "")),
        )
    result["logged_in_user"] = current_user.username
    return result


@router.get("/bulk-uploads/{batch_id}")
def get_bulk_upload_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    batch = get_bulk_batch(db, batch_id)
    if not batch:
        raise http_error(404, "Bulk upload batch not found")
    return {
        "success": True,
        "message": "Bulk upload batch fetched successfully",
        "logged_in_user": current_user.username,
        "batch": batch,
    }


@router.get("/bulk-uploads/{batch_id}/files")
def get_bulk_upload_files(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    batch = get_bulk_batch(db, batch_id)
    if not batch:
        raise http_error(404, "Bulk upload batch not found")
    result = list_bulk_batch_files(db, batch_id, page=page, page_size=page_size)
    items = result["items"]
    if status:
        items = [i for i in items if i.get("status") == status]
    return {
        "success": True,
        "message": "Bulk upload files fetched successfully",
        "logged_in_user": current_user.username,
        "batch_id": batch_id,
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }
