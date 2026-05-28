from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_UPLOAD_READ, PERM_UPLOAD_WRITE
from app.services.audit_service import ACTION_UPLOAD_FILE, log_action
from app.services.upload_service import (
    list_uploads_paginated,
    process_csv_upload,
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
    result = process_csv_upload(db, file, file_path)
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

    items = []
    for file in files:
        validate_upload_file(file)
        file_path = save_upload_file(file)
        result = process_csv_upload(db, file, file_path)
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_UPLOAD_FILE,
            entity_type="upload",
            entity_id=str(result.get("file_id", "")),
        )
        result["logged_in_user"] = current_user.username
        items.append(result)

    return {
        "success": True,
        "message": "Files uploaded",
        "count": len(items),
        "items": items,
        "logged_in_user": current_user.username,
    }
