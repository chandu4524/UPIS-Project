"""OCR processing for PDF and image uploads."""

from __future__ import annotations

import gc
import logging
import math
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, OCR_FOLDER
from app.core.exceptions import http_error
from app.models.ocr_document import OcrDocument
from app.services.ocr_runtime import (
    check_ocr_dependencies,
    configure_pytesseract,
    resolve_poppler_path,
)

logger = logging.getLogger("gpip.ocr")

MAX_OCR_PAGES = int(os.getenv("OCR_MAX_PAGES", "20"))
MAX_OCR_FILE_BYTES = int(os.getenv("OCR_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
OCR_PDF_DPI = int(os.getenv("OCR_PDF_DPI", "150" if APP_ENV in ("production", "prod") else "200"))
OCR_USE_PADDLE = os.getenv("OCR_USE_PADDLE", "false").strip().lower() in ("1", "true", "yes")
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

_paddle_engine = None


def ensure_ocr_folder() -> None:
    os.makedirs(OCR_FOLDER, exist_ok=True)
    logger.debug("OCR folder ensured: %s", OCR_FOLDER)


def assert_ocr_runtime_ready() -> Dict[str, Any]:
    """Fail fast with a clear message when system OCR binaries are missing."""
    status = check_ocr_dependencies()
    if not status.get("ready"):
        logger.error(
            "OCR runtime not ready: tesseract=%s poppler=%s notes=%s",
            status.get("tesseract_binary"),
            status.get("poppler_available"),
            status.get("notes"),
        )
        raise http_error(
            503,
            "OCR is not available on this server. Install Tesseract and Poppler (see deployment docs).",
            status,
        )
    return status


def validate_ocr_file(file: UploadFile) -> None:
    if not file.filename:
        raise http_error(400, "No file provided")
    name = file.filename.lower()
    if not (
        name.endswith(".pdf")
        or name.endswith(".png")
        or name.endswith(".jpg")
        or name.endswith(".jpeg")
    ):
        raise http_error(
            400,
            "Only PDF or image files are supported for OCR processing (PDF, PNG, JPG, JPEG)",
        )


def save_ocr_file(file: UploadFile) -> str:
    ensure_ocr_folder()
    safe_name = os.path.basename(file.filename or "upload")
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(OCR_FOLDER, unique_name)

    size = 0
    with open(file_path, "wb") as buffer:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_OCR_FILE_BYTES:
                buffer.close()
                if os.path.isfile(file_path):
                    os.remove(file_path)
                raise http_error(
                    413,
                    f"File too large for OCR (max {MAX_OCR_FILE_BYTES // (1024 * 1024)} MB)",
                )
            buffer.write(chunk)

    logger.info(
        "OCR file saved path=%s size_bytes=%s filename=%s",
        file_path,
        size,
        safe_name,
    )
    return file_path


def _configure_tesseract() -> None:
    cmd = configure_pytesseract()
    if cmd:
        logger.debug("Tesseract configured path=%s", cmd)


def _ocr_with_pytesseract(image) -> Tuple[str, float]:
    import pytesseract
    from PIL import Image

    _configure_tesseract()
    if not isinstance(image, Image.Image):
        image = Image.fromarray(image)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = []
    confidences = []
    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        if word and str(word).strip():
            words.append(str(word).strip())
            try:
                c = float(conf)
                if c >= 0:
                    confidences.append(c)
            except (TypeError, ValueError):
                pass
    text = " ".join(words)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf


def _get_paddle_engine():
    global _paddle_engine
    if _paddle_engine is None:
        from paddleocr import PaddleOCR

        logger.info("Initializing PaddleOCR engine (one-time)")
        _paddle_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _paddle_engine


def _ocr_with_paddle(image) -> Tuple[str, float]:
    import numpy as np
    from PIL import Image

    if not isinstance(image, Image.Image):
        image = Image.fromarray(image)
    ocr = _get_paddle_engine()
    result = ocr.ocr(np.array(image), cls=True)
    lines = []
    confidences = []
    for block in result or []:
        for line in block or []:
            if line and len(line) >= 2:
                lines.append(line[1][0])
                confidences.append(float(line[1][1]) * 100)
    text = "\n".join(lines)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return text, avg_conf


def _ocr_image(image) -> Tuple[str, float]:
    errors: List[str] = []
    try:
        return _ocr_with_pytesseract(image)
    except Exception as exc:
        errors.append(f"pytesseract: {exc}")
        logger.warning("pytesseract failed: %s", exc)

    if OCR_USE_PADDLE:
        try:
            return _ocr_with_paddle(image)
        except Exception as exc:
            errors.append(f"paddle: {exc}")
            logger.warning("PaddleOCR failed: %s", exc)

    raise http_error(
        500,
        "OCR engine unavailable. Ensure Tesseract is installed and on PATH.",
        "; ".join(errors),
    )


def _pdf_to_images(file_path: str) -> List:
    from pdf2image import convert_from_path

    poppler_path = resolve_poppler_path()
    kwargs = {
        "dpi": OCR_PDF_DPI,
        "first_page": 1,
        "last_page": MAX_OCR_PAGES,
    }
    if poppler_path:
        kwargs["poppler_path"] = poppler_path
        logger.info("Using POPPLER_PATH=%s", poppler_path)

    logger.info(
        "Converting PDF to images path=%s dpi=%s max_pages=%s",
        file_path,
        OCR_PDF_DPI,
        MAX_OCR_PAGES,
    )
    return convert_from_path(file_path, **kwargs)


def _extract_text_pdf_fallback(file_path: str) -> Tuple[str, float]:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return "", 0.0
    reader = PdfReader(file_path)
    parts = []
    for page in reader.pages[:MAX_OCR_PAGES]:
        parts.append(page.extract_text() or "")
    text = "\n\n".join(parts).strip()
    return text, 90.0 if text else 0.0


def extract_table_rows(text: str) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        if "\t" in stripped:
            cells = [c.strip() for c in stripped.split("\t") if c.strip()]
        else:
            cells = [c.strip() for c in re.split(r"\s{2,}", stripped) if c.strip()]
        if len(cells) >= 2:
            rows.append(cells)
    return rows[:500]


def process_pdf_ocr(file_path: str, filename: str) -> Dict[str, Any]:
    page_texts: List[str] = []
    page_confidences: List[float] = []
    engine = "pytesseract"
    pages_processed = 0
    pdf_error: Optional[str] = None

    try:
        images = _pdf_to_images(file_path)
        pages_processed = len(images)
        logger.info("PDF page images ready count=%s file=%s", pages_processed, filename)

        for idx, image in enumerate(images, start=1):
            try:
                text, conf = _ocr_image(image)
                page_texts.append(f"--- Page {idx} ---\n{text}")
                page_confidences.append(conf)
                logger.info(
                    "OCR page %s/%s chars=%s conf=%.1f",
                    idx,
                    pages_processed,
                    len(text or ""),
                    conf,
                )
            finally:
                try:
                    image.close()
                except Exception:
                    pass
            gc.collect()
    except Exception as exc:
        pdf_error = str(exc)
        logger.warning(
            "pdf2image failed for %s (poppler may be missing): %s",
            filename,
            exc,
            exc_info=True,
        )
        engine = "pypdf2_fallback"
        text, conf = _extract_text_pdf_fallback(file_path)
        if text:
            page_texts = [text]
            page_confidences = [conf]
            pages_processed = 1
            logger.info("PyPDF2 text fallback chars=%s", len(text))
        else:
            raise http_error(
                500,
                "Failed to process PDF. For scanned PDFs install Poppler (pdftoppm). "
                "Text-only PDFs may work without Poppler.",
                pdf_error,
            ) from exc

    extracted_text = "\n\n".join(page_texts).strip()
    confidence_score = (
        round(sum(page_confidences) / len(page_confidences), 2)
        if page_confidences
        else 0.0
    )
    table_rows = extract_table_rows(extracted_text)

    return {
        "filename": filename,
        "extracted_text": extracted_text,
        "confidence_score": confidence_score,
        "pages_processed": pages_processed,
        "ocr_engine": engine,
        "table_rows": table_rows,
        "row_count": len(table_rows),
    }


def process_file_ocr(file_path: str, filename: str) -> Dict[str, Any]:
    started = time.perf_counter()
    lower = (filename or "").lower()
    file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
    logger.info(
        "OCR processing start time=%s file=%s size_bytes=%s is_pdf=%s dpi=%s max_pages=%s",
        datetime.utcnow().isoformat() + "Z",
        filename,
        file_size,
        lower.endswith(".pdf"),
        OCR_PDF_DPI,
        MAX_OCR_PAGES,
    )

    if lower.endswith(".pdf"):
        result = process_pdf_ocr(file_path, filename)
        logger.info(
            "OCR processing complete file=%s elapsed_sec=%.2f pages=%s engine=%s",
            filename,
            time.perf_counter() - started,
            result.get("pages_processed"),
            result.get("ocr_engine"),
        )
        return result

    try:
        from PIL import Image
    except Exception as exc:
        raise http_error(500, "Image OCR requires Pillow to be installed", str(exc)) from exc

    image = None
    try:
        image = Image.open(file_path)
        text, conf = _ocr_image(image)
        extracted_text = (text or "").strip()
        table_rows = extract_table_rows(extracted_text)
        elapsed = time.perf_counter() - started
        logger.info(
            "OCR processing complete file=%s elapsed_sec=%.2f chars=%s conf=%.1f engine=image_ocr",
            filename,
            elapsed,
            len(extracted_text),
            conf,
        )
        return {
            "filename": filename,
            "extracted_text": extracted_text,
            "confidence_score": round(float(conf or 0.0), 2),
            "pages_processed": 1,
            "ocr_engine": "image_ocr",
            "table_rows": table_rows,
            "row_count": len(table_rows),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "OCR processing failed file=%s size_bytes=%s elapsed_sec=%.2f error=%s",
            filename,
            file_size,
            time.perf_counter() - started,
            exc,
        )
        raise http_error(
            500,
            "Failed to process image for OCR. Ensure Tesseract is installed (Docker image on Render).",
            str(exc),
        ) from exc
    finally:
        if image is not None:
            try:
                image.close()
            except Exception:
                pass


def ocr_document_to_dict(doc: OcrDocument, include_text: bool = True) -> dict:
    preview = (doc.extracted_text or "")[:280]
    if len(doc.extracted_text or "") > 280:
        preview += "…"
    data = {
        "id": doc.id,
        "filename": doc.filename,
        "confidence_score": doc.confidence_score,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "text_preview": preview,
    }
    if include_text:
        data["extracted_text"] = doc.extracted_text
        data["table_rows"] = extract_table_rows(doc.extracted_text or "")
    return data


def save_ocr_document(db: Session, result: Dict[str, Any]) -> OcrDocument:
    record = OcrDocument(
        filename=result["filename"],
        extracted_text=result.get("extracted_text", ""),
        confidence_score=float(result.get("confidence_score", 0)),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "OCR document saved id=%s filename=%s confidence=%s",
        record.id,
        record.filename,
        record.confidence_score,
    )
    return record


def list_ocr_history(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    query = db.query(OcrDocument)
    total = query.count()
    docs = (
        query.order_by(desc(OcrDocument.created_at), desc(OcrDocument.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return {
        "items": [ocr_document_to_dict(d, include_text=False) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_ocr_document(db: Session, document_id: int) -> Optional[dict]:
    doc = db.query(OcrDocument).filter(OcrDocument.id == document_id).first()
    if not doc:
        return None
    data = ocr_document_to_dict(doc, include_text=True)
    data["json_output"] = {
        "id": doc.id,
        "filename": doc.filename,
        "confidence_score": doc.confidence_score,
        "extracted_text": doc.extracted_text,
        "table_rows": data.get("table_rows", []),
        "created_at": data["created_at"],
    }
    return data
