import os

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_OCR_WRITE
from app.core.exceptions import http_error
from app.services.ocr_service import (
    get_ocr_document,
    list_ocr_history,
    process_pdf_ocr,
    save_ocr_document,
    save_ocr_file,
    validate_ocr_file,
)
from app.utils.dependencies import get_db

router = APIRouter(prefix="/ocr", tags=["OCR"])


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
    validate_ocr_file(file)
    file_path = save_ocr_file(file)
    try:
        result = process_pdf_ocr(file_path, file.filename)
        record = save_ocr_document(db, result)
        return {
            "success": True,
            "message": "PDF processed with OCR successfully",
            "logged_in_user": current_user.username,
            "id": record.id,
            "filename": record.filename,
            "extracted_text": result["extracted_text"],
            "confidence_score": result["confidence_score"],
            "pages_processed": result["pages_processed"],
            "ocr_engine": result["ocr_engine"],
            "table_rows": result["table_rows"],
            "row_count": result["row_count"],
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
    finally:
        if os.path.isfile(file_path):
            os.remove(file_path)
