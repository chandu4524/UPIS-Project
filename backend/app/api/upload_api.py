from typing import List, Optional
import os

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_UPLOAD_READ, PERM_UPLOAD_WRITE
from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.services.audit_service import ACTION_UPLOAD_FILE, log_action
from app.services.data_source_service import resolve_department_name
from app.services.upload_batch_job_service import enqueue_upload_batch, job_status_response
from app.services.upload_service import (
    MAX_MULTI_UPLOAD_FILES,
    list_uploads_paginated,
    process_file_upload,
    save_upload_file,
    validate_upload_file,
)
from app.utils.dependencies import get_db

logger = get_logger("gpip.upload.api")

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


@router.get("/upload-jobs/{job_id}")
def get_upload_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_READ)),
):
    """Poll background multi-file upload job status."""
    payload = job_status_response(db, job_id)
    if not payload:
        raise http_error(404, "Upload job not found")
    payload["logged_in_user"] = current_user.username
    return payload


@router.post("/upload-file")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_WRITE)),
):
    """Single-file upload — synchronous (fast path)."""
    filename = file.filename or "unknown"
    logger.info("upload-file start user=%s filename=%s", current_user.username, filename)
    validate_upload_file(file)
    file_path = save_upload_file(file)
    try:
        result = process_file_upload(db, file, file_path)
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_UPLOAD_FILE,
            entity_type="upload",
            entity_id=str(result.get("file_id", "")),
        )
        result["logged_in_user"] = current_user.username
        logger.info(
            "upload-file complete user=%s filename=%s file_id=%s rows=%s",
            current_user.username,
            filename,
            result.get("file_id"),
            result.get("rows_imported"),
        )
        return result
    except Exception as exc:
        logger.exception(
            "upload-file failed user=%s filename=%s error=%s",
            current_user.username,
            filename,
            exc,
        )
        raise
    finally:
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


@router.post("/upload-files")
def upload_files(
    files: List[UploadFile] = File(...),
    data_source_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_UPLOAD_WRITE)),
):
    """
    Multi-file upload — accepts files, returns job_id immediately.
    Processing continues in a background thread (safe for 50+ mixed files).
    Poll GET /api/upload-jobs/{job_id} for results.
    """
    if not files:
        return {"success": False, "message": "No files provided", "items": []}
    if len(files) > MAX_MULTI_UPLOAD_FILES:
        return {
            "success": False,
            "message": f"Too many files (max {MAX_MULTI_UPLOAD_FILES})",
            "items": [],
        }

    department_name = resolve_department_name(db, data_source_id)
    logger.info(
        "upload-files enqueue user=%s count=%s department=%s",
        current_user.username,
        len(files),
        department_name,
    )

    result = enqueue_upload_batch(
        db,
        files,
        department_name=department_name,
        created_by=current_user.username,
    )
    result["logged_in_user"] = current_user.username
    return result
