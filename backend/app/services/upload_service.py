import math
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple, Optional

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_FOLDER
from app.core.exceptions import http_error
from app.models.citizen import Citizen
from app.models.upload import Upload
from app.services.citizen_service import _load_existing_mobiles
from app.services.normalization_service import (
    empty_normalization_summary,
    normalize_citizen_row,
    normalize_dob,
    _append_preview,
)

REQUIRED_COLUMNS = ["full_name", "mobile", "district", "village", "dob"]
MAX_VALIDATION_ERRORS = 100


def normalize_header(header):
    return (
        str(header)
        .strip()
        .lower()
        .replace("-", "*")
        .replace(" ", "*")
    )


HEADER_ALIASES = {
    "full_name": [
        "full_name",
        "full name",
        "name",
        "customer_name",
        "consumer_name",
        "person_name",
        "citizen_name",
    ],
    "mobile": [
        "mobile",
        "mobile_no",
        "mobile_number",
        "phone",
        "phone_number",
        "contact",
    ],
    "district": [
        "district",
        "district_name",
    ],
    "village": [
        "village",
        "village_name",
        "town",
        "area",
        "location",
    ],
    "dob": [
        "dob",
        "date_of_birth",
        "birth_date",
        "date of birth",
        "birthdate",
        "age_dob",
    ],
}


def canonicalize_columns(df):
    renamed = {}
    normalized_cols = {
        normalize_header(c): c
        for c in df.columns
    }

    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            key = normalize_header(alias)
            if key in normalized_cols:
                renamed[normalized_cols[key]] = canonical
                break

    return df.rename(columns=renamed)

DOB_PATTERNS = (
    re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
    re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"),
    re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"),
)
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _upload_status(upload: Upload) -> str:
    if upload.uploaded_rows > 0:
        return "Completed"
    return "No records"


def upload_to_dict(upload: Upload) -> dict:
    uploaded_by = getattr(upload, "uploaded_by", None)
    return {
        "id": upload.id,
        "filename": upload.filename,
        "uploaded_rows": upload.uploaded_rows,
        "uploaded_at": upload.uploaded_at,
        "status": _upload_status(upload),
        "uploaded_by": uploaded_by,
    }


def list_uploads_paginated(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    query = db.query(Upload)
    total = query.count()

    uploads = (
        query.order_by(desc(Upload.uploaded_at), desc(Upload.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0

    return {
        "items": [upload_to_dict(u) for u in uploads],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def ensure_upload_folder():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def validate_upload_file(file: UploadFile) -> None:
    if not file.filename:
        raise http_error(400, "No file provided")
    if not file.filename.lower().endswith(".csv"):
        raise http_error(400, "Only CSV files are allowed")


def validate_csv_columns(file_path: str) -> None:
    try:
        df = pd.read_csv(file_path, nrows=1)
    except Exception as exc:
        raise http_error(400, "Invalid CSV file", str(exc)) from exc

    df = canonicalize_columns(df)
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return df, missing_columns


def _cell_empty(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return not str(value).strip()


def _is_valid_dob(value) -> bool:
    if _cell_empty(value):
        return False
    _, ok = normalize_dob(value)
    return ok


def _append_error(
    errors: List[dict],
    row_number: int,
    error_type: str,
    description: str,
) -> None:
    if len(errors) >= MAX_VALIDATION_ERRORS:
        return
    errors.append(
        {
            "row_number": row_number,
            "error_type": error_type,
            "description": description,
        }
    )


def validate_and_import_citizens(db: Session, df: pd.DataFrame) -> Dict[str, Any]:
    return validate_and_import_citizens_iter(db, [df])


def validate_and_import_citizens_iter(
    db: Session, chunks: Iterable[pd.DataFrame]
) -> Dict[str, Any]:
    """
    Validate each CSV row (streaming over chunks), import valid records,
    and return a quality summary.
    """
    existing_mobiles = _load_existing_mobiles(db)
    seen_in_file: set = set()
    errors: List[dict] = []
    valid_rows = 0
    invalid_rows = 0
    duplicate_rows = 0
    citizens_to_add: List[Citizen] = []
    norm_summary = empty_normalization_summary()
    preview = norm_summary["preview"]
    total_rows = 0
    current_row_number = 2  # header is row 1

    for df in chunks:
        if df is None or df.empty:
            continue
        # ensure stable order to keep row_number consistent
        df = df.reset_index(drop=True)
        for _, row in df.iterrows():
            row_number = current_row_number
            current_row_number += 1
            total_rows += 1
        row_errors: List[Tuple[str, str]] = []
        row_dict = row.to_dict()
        norm = normalize_citizen_row(row_dict)
        originals = norm["originals"]
        normalized = norm["normalized"]

        missing_fields = [
            col for col in REQUIRED_COLUMNS if _cell_empty(row.get(col))
        ]
        if missing_fields:
            row_errors.append(
                (
                    "MISSING_REQUIRED_FIELD",
                    f"Missing required field(s): {', '.join(missing_fields)}",
                )
            )
        elif not normalized["full_name"]:
            row_errors.append(("EMPTY_NAME", "Full name cannot be empty"))

        if not _cell_empty(row.get("dob")) and not norm["dob_valid"]:
            row_errors.append(
                (
                    "INVALID_DOB",
                    "Date of birth must use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD format",
                )
            )

        if row_errors:
            invalid_rows += 1
            for error_type, description in row_errors:
                _append_error(errors, row_number, error_type, description)
            continue

        mobile = normalized["mobile"]
        if mobile in existing_mobiles or mobile in seen_in_file:
            duplicate_rows += 1
            _append_error(
                errors,
                row_number,
                "DUPLICATE_MOBILE",
                f"Duplicate mobile number: {mobile}",
            )
            continue

        if norm["changes"]["name_changed"]:
            norm_summary["names_normalized"] += 1
            _append_preview(
                preview, row_number, "full_name", originals["full_name"], normalized["full_name"]
            )
        if norm["changes"]["phone_changed"]:
            norm_summary["phones_normalized"] += 1
            _append_preview(
                preview, row_number, "mobile", originals["mobile"], normalized["mobile"]
            )
        if norm["changes"]["dob_changed"]:
            norm_summary["dates_normalized"] += 1
            _append_preview(preview, row_number, "dob", originals["dob"], normalized["dob"])

        if norm["matching_key"]:
            norm_summary["matching_keys_generated"] += 1

        citizen = Citizen(
            full_name=normalized["full_name"],
            mobile=mobile,
            district=normalized["district"],
            village=normalized["village"],
            dob=normalized["dob"],
        )
        citizens_to_add.append(citizen)
        existing_mobiles.add(mobile)
        seen_in_file.add(mobile)
        valid_rows += 1

        # Commit in batches so very large files don't blow memory
        if len(citizens_to_add) >= 5000:
            db.add_all(citizens_to_add)
            db.commit()
            citizens_to_add.clear()

    if citizens_to_add:
        db.add_all(citizens_to_add)
        db.commit()

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows,
        "errors": errors,
        "rows_imported": valid_rows,
        "rows_skipped": invalid_rows + duplicate_rows,
        "normalization": norm_summary,
    }


def save_upload_file(file: UploadFile) -> str:
    ensure_upload_folder()
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


def process_csv_upload(
    db: Session,
    file: UploadFile,
    file_path: str,
) -> dict:
    df, missing = validate_csv_columns(file_path)
    if missing:
        raise http_error(
            400,
            "CSV is missing required columns",
            {
                "missing_columns": missing,
                "required_columns": REQUIRED_COLUMNS,
                "found_columns": list(df.columns),
            },
        )

    # Stream the CSV in chunks (supports very large files)
    chunk_iter = pd.read_csv(file_path, chunksize=50000)
    missing_value_counts: Dict[str, int] = {c: 0 for c in REQUIRED_COLUMNS}
    preview_rows: Optional[List[Dict[str, Any]]] = None

    def _normalized_chunks() -> Iterable[pd.DataFrame]:
        nonlocal preview_rows
        for chunk in chunk_iter:
            chunk = canonicalize_columns(chunk)
            if preview_rows is None and not chunk.empty:
                preview_rows = chunk.head(5).to_dict(orient="records")
            for c in REQUIRED_COLUMNS:
                if c in chunk.columns:
                    # pandas vectorization isn't perfect here because _cell_empty is custom,
                    # but the chunk size keeps this fast enough.
                    missing_value_counts[c] += int(chunk[c].apply(_cell_empty).sum())
            yield chunk

    validation = validate_and_import_citizens_iter(db, _normalized_chunks())
    rows_imported = validation["rows_imported"]
    rows_skipped = validation["rows_skipped"]

    upload_record = Upload(
        filename=file.filename,
        uploaded_rows=rows_imported,
        uploaded_at=datetime.utcnow(),
    )
    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)

    total_rows = validation["total_rows"] or 0
    missing_values = {
        c: {
            "missing": int(missing_value_counts.get(c, 0)),
            "total_rows": int(total_rows),
            "percent": (float(missing_value_counts.get(c, 0)) / float(total_rows) * 100.0)
            if total_rows
            else 0.0,
        }
        for c in REQUIRED_COLUMNS
    }

    return {
        "success": True,
        "message": "Upload completed with validation results",
        "file_id": upload_record.id,
        "filename": file.filename,
        "preview_data": preview_rows or [],
        "rows_imported": rows_imported,
        "rows_skipped": rows_skipped,
        "total_rows": validation["total_rows"],
        "valid_rows": validation["valid_rows"],
        "invalid_rows": validation["invalid_rows"],
        "duplicate_rows": validation["duplicate_rows"],
        "errors": validation["errors"],
        "normalization": validation.get("normalization", empty_normalization_summary()),
        "required_columns": REQUIRED_COLUMNS,
        "found_columns": list(df.columns),
        "missing_values": missing_values,
    }
