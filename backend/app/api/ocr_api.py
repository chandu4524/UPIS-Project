import os
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_OCR_WRITE
from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.services.ocr_runtime import build_ocr_status_payload
from app.services.ocr_service import (
    assert_ocr_runtime_ready,
    get_ocr_document,
    list_ocr_history,
    process_file_ocr,
    save_ocr_document,
    save_ocr_file,
    validate_ocr_file,
)
from app.utils.dependencies import get_db

logger = get_logger("gpip.ocr.api")

router = APIRouter(prefix="/ocr", tags=["OCR"])


def _ocr_status_response(*, logged_in_user: Optional[str] = None) -> dict:
    payload = build_ocr_status_payload()
    body = {
        "success": True,
        "ocr_ready": payload["ocr_ready"],
        "tesseract_binary": payload["tesseract_binary"],
        "poppler_available": payload["poppler_available"],
        "tesseract_path": payload.get("tesseract_path"),
        "poppler_path": payload.get("poppler_path"),
        "dependencies": payload.get("dependencies"),
        "config": payload.get("config"),
    }
    if logged_in_user:
        body["logged_in_user"] = logged_in_user
    return body


@router.get("/health")
def ocr_health():
    """
    Public OCR readiness probe (no auth).
    Use for Render health checks and deployment verification.
    """
    payload = build_ocr_status_payload()
    status_code = 200 if payload["ocr_ready"] else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "success": payload["ocr_ready"],
            "ocr_ready": payload["ocr_ready"],
            "tesseract_binary": payload["tesseract_binary"],
            "poppler_available": payload["poppler_available"],
            "tesseract_path": payload.get("tesseract_path"),
            "poppler_path": payload.get("poppler_path"),
        },
    )


@router.get("/status")
def ocr_status(
    current_user: CurrentUser = Depends(require_permission(PERM_OCR_WRITE)),
):
    """Authenticated OCR runtime readiness (same fields as /health)."""
    return _ocr_status_response(logged_in_user=current_user.username)


@router.get("/status/{document_id}")
def ocr_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_OCR_WRITE)),
):
    """Processing status for a single OCR document."""
    data = get_ocr_document(db, document_id)
    if not data:
        raise http_error(404, "OCR document not found")
    return {
        "success": True,
        "message": "OCR document status fetched successfully",
        "logged_in_user": current_user.username,
        "status": "completed",
        **data,
    }


@router.get("/history")
def ocr_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_OCR_WRITE)),
):
    result = list_ocr_history(db, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "OCR history fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/{document_id}")
def ocr_detail(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_OCR_WRITE)),
):
    data = get_ocr_document(db, document_id)
    if not data:
        raise http_error(404, "OCR document not found")
    return {
        "success": True,
        "message": "OCR document fetched successfully",
        "logged_in_user": current_user.username,
        **data,
    }


@router.post("/upload")
def ocr_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_OCR_WRITE)),
):
    started = time.perf_counter()
    start_iso = datetime.utcnow().isoformat() + "Z"
    filename = file.filename or "unknown"
    content_type = file.content_type
    file_path = None

    logger.info(
        "OCR upload start time=%s user=%s filename=%s content_type=%s",
        start_iso,
        current_user.username,
        filename,
        content_type,
    )

    try:
        status = build_ocr_status_payload()
        logger.info(
            "OCR preflight ocr_ready=%s tesseract=%s poppler=%s tesseract_path=%s poppler_path=%s",
            status["ocr_ready"],
            status["tesseract_binary"],
            status["poppler_available"],
            status.get("tesseract_path"),
            status.get("poppler_path"),
        )

        assert_ocr_runtime_ready()
        validate_ocr_file(file)

        file_path = save_ocr_file(file)
        saved_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
        logger.info(
            "OCR file saved filename=%s path=%s size_bytes=%s",
            filename,
            file_path,
            saved_size,
        )

        result = process_file_ocr(file_path, filename)
        record = save_ocr_document(db, result)

        elapsed = time.perf_counter() - started
        complete_iso = datetime.utcnow().isoformat() + "Z"
        logger.info(
            "OCR upload complete start=%s end=%s id=%s user=%s filename=%s size_bytes=%s "
            "pages=%s engine=%s confidence=%.1f elapsed_sec=%.2f",
            start_iso,
            complete_iso,
            record.id,
            current_user.username,
            filename,
            saved_size,
            result.get("pages_processed"),
            result.get("ocr_engine"),
            float(result.get("confidence_score") or 0),
            elapsed,
        )

        return {
            "success": True,
            "message": "Document processed with OCR successfully",
            "logged_in_user": current_user.username,
            "id": record.id,
            "filename": record.filename,
            "extracted_text": result["extracted_text"],
            "confidence_score": result["confidence_score"],
            "pages_processed": result["pages_processed"],
            "ocr_engine": result["ocr_engine"],
            "table_rows": result["table_rows"],
            "row_count": result["row_count"],
            "diagnostics": {
                "start_time": start_iso,
                "completion_time": complete_iso,
                "elapsed_seconds": round(elapsed, 2),
                "file_size_bytes": saved_size,
            },
            "json_output": {
                "id": record.id,
                "filename": record.filename,
                "confidence_score": result["confidence_score"],
                "extracted_text": result["extracted_text"],
                "table_rows": result["table_rows"],
                "pages_processed": result["pages_processed"],
                "ocr_engine": result["ocr_engine"],
            },
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.exception(
            "OCR upload failed start=%s user=%s filename=%s elapsed_sec=%.2f error=%s",
            start_iso,
            current_user.username,
            filename,
            elapsed,
            exc,
        )
        raise
    finally:
        if file_path and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                logger.debug("OCR temp file removed path=%s", file_path)
            except OSError as remove_err:
                logger.warning("Failed to remove OCR temp file %s: %s", file_path, remove_err)
