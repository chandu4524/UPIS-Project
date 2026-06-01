from typing import List, Optional
import os

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_UPLOAD_READ, PERM_UPLOAD_WRITE
from app.services.audit_service import ACTION_UPLOAD_FILE, log_action
from app.services.data_source_service import resolve_department_name
from app.services.upload_service import (
    list_uploads_paginated,
    process_file_upload,
    process_upload_file_item,
    save_upload_file,
    validate_upload_file,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["File Upload"])


@router.get("/uploads")
def get_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    result = list_uploads_paginated(db, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Upload history fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.post("/upload-file")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_WRITE)),
):
    validate_upload_file(file)
    file_path = save_upload_file(file)
    result = process_file_upload(db, file, file_path)
    log_action(
        db,
        username=current_user.username,
        action_type=ACTION_UPLOAD_FILE,
        entity_type="upload",
        entity_id=str(result.get("file_id", "")),
    )
    result["logged_in_user"] = current_user.username
    return result


@router.post("/upload-files")
def upload_files(
    files: List[UploadFile] = File(...),
    data_source_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_WRITE)),
):
    if not files:
        return {"success": False, "message": "No files provided", "items": []}
    if len(files) > 30:
        # Keep limit server-side too
        return {
            "success": False,
            "message": "Too many files (max 30)",
            "items": [],
        }

    department_name = resolve_department_name(db, data_source_id)

    items = []
    for file in files:
        file_path = None
        try:
            file_path = save_upload_file(file)
            item = process_upload_file_item(
                db,
                file,
                file_path,
                department_name=department_name,
            )
            if item.get("status") == "success" and item.get("file_id"):
                log_action(
                    db,
                    username=current_user.username,
                    action_type=ACTION_UPLOAD_FILE,
                    entity_type="upload",
                    entity_id=str(item.get("file_id", "")),
                )
            items.append(item)
        finally:
            if file_path and os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    succeeded = sum(1 for item in items if item.get("upload_success") or item.get("status") == "success")
    failed = len(items) - succeeded
    analytics_warnings = [
        item.get("analytics_warning")
        for item in items
        if item.get("analytics_warning") and (item.get("upload_success") or item.get("status") == "success")
    ]

    validation_warnings = [
        item.get("validation_warning")
        for item in items
        if item.get("validation_warning") and (item.get("upload_success") or item.get("status") == "success")
    ]

    return {
        "success": failed == 0,
        "upload_success": succeeded > 0,
        "message": (
            f"Processed {len(items)} file(s): {succeeded} succeeded, {failed} failed"
            if failed
            else "Files uploaded"
        ),
        "analytics_warning": analytics_warnings[0] if len(analytics_warnings) == 1 else (
            f"Analytics sync warnings on {len(analytics_warnings)} file(s)" if analytics_warnings else None
        ),
        "validation_warning": validation_warnings[0] if len(validation_warnings) == 1 else (
            f"Duplicate records skipped in {len(validation_warnings)} file(s)" if validation_warnings else None
        ),
        "count": len(items),
        "items": items,
        "logged_in_user": current_user.username,
    }
