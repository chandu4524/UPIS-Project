"""Background multi-file upload jobs — return batch ID immediately, process on a worker thread."""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_FOLDER
from app.core.logging_config import get_logger
from app.database.connection import SessionLocal
from app.models.upload_batch import UploadBatch, UploadBatchFile
from app.services.audit_service import ACTION_UPLOAD_FILE, log_action
from app.services.bulk_upload_service import (
    MAX_BULK_FILES,
    _batch_file_to_dict,
    _batch_to_dict,
    create_bulk_batch,
)
from app.services.upload_service import (
    ensure_upload_folder,
    process_upload_file_item,
    validate_upload_file,
)

logger = get_logger("gpip.upload.job")

BATCH_STAGING_DIR = "batch_jobs"
_TERMINAL_BATCH_STATUSES = frozenset({"completed", "partial_failure", "failed"})


class _SavedUpload:
    """Minimal stand-in for UploadFile when processing saved batch files."""

    def __init__(self, filename: str):
        self.filename = filename


def _batch_staging_path(batch_id: int) -> str:
    path = os.path.join(UPLOAD_FOLDER, BATCH_STAGING_DIR, str(batch_id))
    os.makedirs(path, exist_ok=True)
    return path


def _save_batch_file(batch_id: int, file: UploadFile) -> str:
    """Persist uploaded bytes to batch staging before the HTTP request ends."""
    staging = _batch_staging_path(batch_id)
    safe_name = os.path.basename(file.filename or "upload")
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
    dest = os.path.join(staging, unique_name)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


def _cleanup_batch_staging(batch_id: int) -> None:
    staging = os.path.join(UPLOAD_FOLDER, BATCH_STAGING_DIR, str(batch_id))
    if os.path.isdir(staging):
        try:
            shutil.rmtree(staging, ignore_errors=True)
        except OSError as exc:
            logger.warning("batch staging cleanup failed batch_id=%s error=%s", batch_id, exc)


def batch_file_to_upload_item(batch_file: Dict[str, Any]) -> Dict[str, Any]:
    """Map batch file record to legacy /upload-files item shape for the frontend."""
    status = batch_file.get("status") or "queued"
    filename = batch_file.get("filename") or "unknown"

    if status == "completed":
        return {
            "file_name": filename,
            "status": "success",
            "upload_success": True,
            "file_id": batch_file.get("upload_id"),
            "rows_processed": int(batch_file.get("total_rows") or batch_file.get("rows_imported") or 0),
            "validation_results": {
                "total_rows": batch_file.get("total_rows"),
                "valid_rows": batch_file.get("valid_rows"),
                "invalid_rows": batch_file.get("rejected_rows"),
                "rows_imported": batch_file.get("rows_imported"),
            },
            "error": "",
            "message": "Upload completed",
        }

    if status == "failed":
        return {
            "file_name": filename,
            "status": "failed",
            "upload_success": False,
            "file_id": batch_file.get("upload_id"),
            "rows_processed": 0,
            "validation_results": None,
            "error": batch_file.get("error_message") or "Upload failed",
            "message": "",
        }

    return {
        "file_name": filename,
        "status": "processing",
        "upload_success": False,
        "file_id": None,
        "rows_processed": 0,
        "validation_results": None,
        "error": "",
        "message": "Processing…",
    }


def job_status_response(db: Session, batch_id: int) -> Optional[Dict[str, Any]]:
    batch = db.query(UploadBatch).filter(UploadBatch.id == int(batch_id)).first()
    if not batch:
        return None

    files = (
        db.query(UploadBatchFile)
        .filter(UploadBatchFile.batch_id == batch.id)
        .order_by(UploadBatchFile.id.asc())
        .all()
    )
    file_dicts = [_batch_file_to_dict(f) for f in files]
    items = [batch_file_to_upload_item(f) for f in file_dicts]

    succeeded = sum(1 for f in files if f.status == "completed")
    failed = sum(1 for f in files if f.status == "failed")
    processing = batch.total_files - succeeded - failed

    return {
        "success": True,
        "job_id": batch.id,
        "batch_id": batch.id,
        "status": batch.status,
        "processing": processing > 0,
        "message": _job_message(batch.status, succeeded, failed, batch.total_files),
        "batch": _batch_to_dict(batch, files),
        "items": items,
        "succeeded": succeeded,
        "failed": failed,
        "processing_count": processing,
        "count": len(items),
        "upload_success": succeeded > 0,
        "partial_success": succeeded > 0 and failed > 0,
    }


def _job_message(status: str, succeeded: int, failed: int, total: int) -> str:
    if status == "processing":
        done = succeeded + failed
        return f"Processing upload job ({done}/{total} files complete)…"
    if status == "completed":
        return f"All {total} file(s) uploaded successfully."
    if status == "partial_failure":
        return f"Processed {total} file(s): {succeeded} succeeded, {failed} failed."
    if status == "failed":
        return f"Upload job failed ({failed} of {total} file(s))."
    return "Upload job status unknown."


def enqueue_upload_batch(
    db: Session,
    files: List[UploadFile],
    *,
    department_name: Optional[str],
    created_by: str,
) -> Dict[str, Any]:
    """
    Save files, create batch records, and start background processing.
    Returns immediately with job_id for polling.
    """
    if not files:
        return {"success": False, "message": "No files provided"}
    if len(files) > MAX_BULK_FILES:
        return {
            "success": False,
            "message": f"Too many files (max {MAX_BULK_FILES})",
        }

    ensure_upload_folder()
    batch = create_bulk_batch(db, created_by=created_by, file_count=len(files))
    batch.notes = json.dumps({"department_name": department_name})
    db.commit()

    queued: List[Dict[str, str]] = []
    for file in files:
        filename = file.filename or "unknown"
        try:
            validate_upload_file(file)
            file_path = _save_batch_file(batch.id, file)
            batch_file = UploadBatchFile(
                batch_id=batch.id,
                filename=filename,
                file_format="pending",
                source_type=department_name or "general",
                status="queued",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(batch_file)
            db.commit()
            db.refresh(batch_file)
            queued.append({"batch_file_id": str(batch_file.id), "path": file_path, "filename": filename})
        except Exception as exc:
            logger.exception("enqueue failed filename=%s error=%s", filename, exc)
            fail = UploadBatchFile(
                batch_id=batch.id,
                filename=filename,
                file_format="unknown",
                source_type=department_name or "general",
                status="failed",
                error_message=str(exc),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(fail)
            batch.failed_files = int(batch.failed_files or 0) + 1
            db.commit()

    db.refresh(batch)
    logger.info(
        "upload job enqueued job_id=%s user=%s queued=%s failed_enqueue=%s",
        batch.id,
        created_by,
        len(queued),
        batch.failed_files,
    )

    if queued:
        thread = threading.Thread(
            target=_run_batch_job,
            args=(batch.id, department_name, created_by, queued),
            daemon=True,
            name=f"upload-batch-{batch.id}",
        )
        thread.start()
    else:
        batch.status = "failed"
        batch.updated_at = datetime.utcnow()
        db.commit()

    return {
        "success": True,
        "async": True,
        "job_id": batch.id,
        "batch_id": batch.id,
        "status": batch.status,
        "message": "Upload job accepted — processing in background",
        "poll_url": f"/api/upload-jobs/{batch.id}",
        "total_files": batch.total_files,
    }


def _run_batch_job(
    batch_id: int,
    department_name: Optional[str],
    created_by: str,
    queued: List[Dict[str, str]],
) -> None:
    db = SessionLocal()
    try:
        _process_batch_job(db, batch_id, department_name, created_by, queued)
    except Exception as exc:
        logger.exception("upload job crashed job_id=%s error=%s", batch_id, exc)
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if batch and batch.status == "processing":
            batch.status = "failed"
            batch.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
        _cleanup_batch_staging(batch_id)


def _process_batch_job(
    db: Session,
    batch_id: int,
    department_name: Optional[str],
    created_by: str,
    queued: List[Dict[str, str]],
) -> None:
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        return

    logger.info("upload job started job_id=%s files=%s", batch_id, len(queued))

    for entry in queued:
        batch_file = (
            db.query(UploadBatchFile)
            .filter(UploadBatchFile.id == int(entry["batch_file_id"]))
            .first()
        )
        if not batch_file:
            continue

        filename = entry["filename"]
        file_path = entry["path"]
        batch_file.status = "processing"
        batch_file.updated_at = datetime.utcnow()
        db.commit()

        try:
            saved = _SavedUpload(filename)
            item = process_upload_file_item(
                db,
                saved,
                file_path,
                department_name=department_name,
            )
            if item.get("status") == "success" and item.get("file_id"):
                batch_file.upload_id = item.get("file_id")
                batch_file.status = "completed"
                validation = item.get("validation_results") or {}
                batch_file.total_rows = int(validation.get("total_rows") or item.get("rows_processed") or 0)
                batch_file.valid_rows = int(validation.get("valid_rows") or 0)
                batch_file.rows_imported = int(validation.get("rows_imported") or validation.get("inserted_records") or 0)
                batch_file.rejected_rows = int(validation.get("rejected_rows") or validation.get("invalid_rows") or 0)
                batch_file.partial_rows = int(validation.get("partial_rows") or 0)
                batch_file.error_message = None
                batch.completed_files = int(batch.completed_files or 0) + 1
                log_action(
                    db,
                    username=created_by,
                    action_type=ACTION_UPLOAD_FILE,
                    entity_type="upload",
                    entity_id=str(item.get("file_id", "")),
                )
                logger.info(
                    "upload job file complete job_id=%s filename=%s upload_id=%s",
                    batch_id,
                    filename,
                    item.get("file_id"),
                )
            else:
                batch_file.status = "failed"
                batch_file.error_message = item.get("error") or "Upload failed"
                batch.failed_files = int(batch.failed_files or 0) + 1
                logger.warning(
                    "upload job file failed job_id=%s filename=%s error=%s",
                    batch_id,
                    filename,
                    batch_file.error_message,
                )
        except Exception as exc:
            batch_file.status = "failed"
            batch_file.error_message = str(exc)
            batch.failed_files = int(batch.failed_files or 0) + 1
            logger.exception("upload job file error job_id=%s filename=%s", batch_id, filename)

        batch_file.updated_at = datetime.utcnow()
        batch.updated_at = datetime.utcnow()
        db.commit()

        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    db.refresh(batch)
    done = int(batch.completed_files or 0) + int(batch.failed_files or 0)
    if done >= batch.total_files:
        if batch.failed_files == 0:
            batch.status = "completed"
        elif batch.completed_files == 0:
            batch.status = "failed"
        else:
            batch.status = "partial_failure"
        batch.updated_at = datetime.utcnow()
        db.commit()

    logger.info(
        "upload job finished job_id=%s status=%s completed=%s failed=%s",
        batch_id,
        batch.status,
        batch.completed_files,
        batch.failed_files,
    )


def is_terminal_batch_status(status: str) -> bool:
    return status in _TERMINAL_BATCH_STATUSES
