import math
import os
import re
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import OCR_FOLDER
from app.core.exceptions import http_error
from app.models.ocr_document import OcrDocument

MAX_OCR_PAGES = 20
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def ensure_ocr_folder() -> None:
    os.makedirs(OCR_FOLDER, exist_ok=True)


def validate_ocr_file(file: UploadFile) -> None:
    if not file.filename:
        raise http_error(400, "No file provided")
    name = file.filename.lower()
    if not (name.endswith(".pdf") or name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg")):
        raise http_error(400, "Only PDF or image files are supported for OCR processing (PDF, PNG, JPG, JPEG)")


def save_ocr_file(file: UploadFile) -> str:
    ensure_ocr_folder()
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(OCR_FOLDER, unique_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


def _ocr_with_pytesseract(image) -> Tuple[str, float]:
    import pytesseract
    from PIL import Image

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


def _ocr_with_paddle(image) -> Tuple[str, float]:
    import numpy as np
    from paddleocr import PaddleOCR
    from PIL import Image

    if not isinstance(image, Image.Image):
        image = Image.fromarray(image)
    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
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
    try:
        return _ocr_with_pytesseract(image)
    except Exception:
        try:
            return _ocr_with_paddle(image)
        except Exception as exc:
            raise http_error(
                500,
                "OCR engine unavailable. Install Tesseract OCR and Poppler, or PaddleOCR.",
                str(exc),
            ) from exc


def _pdf_to_images(file_path: str) -> List:
    from pdf2image import convert_from_path

    return convert_from_path(file_path, dpi=200, first_page=1, last_page=MAX_OCR_PAGES)


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

    try:
        images = _pdf_to_images(file_path)
        pages_processed = len(images)
        for idx, image in enumerate(images, start=1):
            text, conf = _ocr_image(image)
            page_texts.append(f"--- Page {idx} ---\n{text}")
            page_confidences.append(conf)
    except Exception:
        engine = "pypdf2_fallback"
        text, conf = _extract_text_pdf_fallback(file_path)
        if text:
            page_texts = [text]
            page_confidences = [conf]
            pages_processed = 1
        else:
            raise http_error(
                500,
                "Failed to process PDF. Ensure Poppler is installed for scanned PDFs.",
            )

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
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return process_pdf_ocr(file_path, filename)

    try:
        from PIL import Image
    except Exception as exc:
        raise http_error(500, "Image OCR requires Pillow to be installed", str(exc)) from exc

    try:
        image = Image.open(file_path)
        text, conf = _ocr_image(image)
        extracted_text = (text or "").strip()
        table_rows = extract_table_rows(extracted_text)
        return {
            "filename": filename,
            "extracted_text": extracted_text,
            "confidence_score": round(float(conf or 0.0), 2),
            "pages_processed": 1,
            "ocr_engine": "image_ocr",
            "table_rows": table_rows,
            "row_count": len(table_rows),
        }
    except Exception as exc:
        raise http_error(500, "Failed to process image for OCR", str(exc)) from exc


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
