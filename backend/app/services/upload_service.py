import math
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple, Optional

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_FOLDER
from app.core.exceptions import http_error
from app.models.citizen import Citizen
from app.models.person_staging import PersonStaging
from app.models.upload import Upload
from app.services.citizen_service import (
    _load_existing_mobiles,
    get_citizen_by_mobile,
    mobile_lookup_key,
    safe_insert_citizen,
)
from app.services.normalization_service import (
    empty_normalization_summary,
    normalize_citizen_row,
    normalize_dob,
    _append_preview,
)
from app.services.staging_service import build_staging_row
from app.services.entity_resolution_service_v2 import generate_candidates_for_upload
from app.services.header_canonicalization import (
    CORE_IMPORT_COLUMNS,
    build_column_mapping,
    canonicalize_columns,
)
from app.services.file_ingestion_service import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_FORMATS_MESSAGE,
    is_supported_upload,
    load_file_as_dataframe,
    register_ingested_dataframe,
)

REQUIRED_COLUMNS = CORE_IMPORT_COLUMNS
MAX_VALIDATION_ERRORS = 100
ALLOWED_UPLOAD_EXTENSIONS = SUPPORTED_EXTENSIONS
UPLOAD_CHUNK_SIZE = 50000

DOB_PATTERNS = (
    re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
    re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"),
    re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"),
)
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _upload_status(upload: Upload, staged_count: int = 0) -> str:
    if (upload.uploaded_rows or 0) > 0 or staged_count > 0:
        return "Completed"
    return "No records"


def upload_to_dict(upload: Upload, staged_count: int = 0) -> dict:
    uploaded_by = getattr(upload, "uploaded_by", None)
    imported_rows = int(upload.uploaded_rows or 0)
    processed_rows = max(imported_rows, int(staged_count or 0))
    return {
        "id": upload.id,
        "filename": upload.filename,
        "uploaded_rows": processed_rows,
        "imported_rows": imported_rows,
        "uploaded_at": upload.uploaded_at.isoformat() if upload.uploaded_at else None,
        "status": _upload_status(upload, staged_count),
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

    upload_ids = [u.id for u in uploads]
    staging_counts: Dict[int, int] = {}
    if upload_ids:
        staging_counts = dict(
            db.query(PersonStaging.upload_batch_id, func.count(PersonStaging.id))
            .filter(PersonStaging.upload_batch_id.in_(upload_ids))
            .group_by(PersonStaging.upload_batch_id)
            .all()
        )

    return {
        "items": [upload_to_dict(u, staging_counts.get(u.id, 0)) for u in uploads],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def ensure_upload_folder():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _upload_error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            message = str(detail.get("message") or "Upload failed")
            extra = detail.get("detail")
            if extra and str(extra).strip():
                return f"{message}: {extra}"
            return message
        return str(detail or exc)
    return str(exc)


def _build_analytics_warning(
    chunk_warnings: List[str],
    summary_warning: Optional[str],
) -> Optional[str]:
    parts: List[str] = []
    if chunk_warnings:
        unique = list(dict.fromkeys(w for w in chunk_warnings if w))
        if len(unique) == 1:
            parts.append(unique[0])
        else:
            parts.append(f"DuckDB row sync failed for {len(chunk_warnings)} chunk(s)")
    if summary_warning:
        parts.append(summary_warning)
    return "; ".join(parts) if parts else None


def file_upload_item_from_result(filename: str, result: Dict[str, Any]) -> Dict[str, Any]:
    upload_success = bool(result.get("upload_success", result.get("success", True)))
    validation = result.get("validation_results") or {
        "total_rows": result.get("total_rows"),
        "valid_rows": result.get("valid_rows"),
        "invalid_rows": result.get("invalid_rows"),
        "duplicate_rows": result.get("duplicate_rows"),
        "duplicate_records": result.get("duplicate_records"),
        "inserted_records": result.get("inserted_records"),
        "skipped_duplicates": result.get("skipped_duplicates"),
        "rows_imported": result.get("rows_imported"),
        "rows_skipped": result.get("rows_skipped"),
        "staged_rows": result.get("staged_rows"),
        "rejected_rows": result.get("rejected_rows"),
        "partial_rows": result.get("partial_rows"),
    }
    rows_processed = int(
        validation.get("total_rows")
        or result.get("total_rows")
        or result.get("staged_rows")
        or result.get("rows_imported")
        or 0
    )
    skipped_duplicates = int(validation.get("skipped_duplicates") or validation.get("duplicate_rows") or 0)
    validation_warning = None
    if skipped_duplicates > 0:
        validation_warning = (
            f"{skipped_duplicates} duplicate mobile number(s) skipped; "
            "upload completed successfully."
        )
    return {
        "file_name": filename,
        "status": "success" if upload_success else "failed",
        "upload_success": upload_success,
        "validation_results": validation,
        "validation_warning": result.get("validation_warning") or validation_warning,
        "analytics_warning": result.get("analytics_warning"),
        "message": result.get("message") or "Upload completed with validation results",
        "error": "",
        "rows_processed": rows_processed,
        "file_id": result.get("file_id"),
    }


def file_upload_item_from_error(filename: str, exc: Exception) -> Dict[str, Any]:
    return {
        "file_name": filename,
        "status": "failed",
        "upload_success": False,
        "validation_results": None,
        "analytics_warning": None,
        "message": "",
        "error": _upload_error_message(exc),
        "rows_processed": 0,
        "file_id": None,
    }


def process_upload_file_item(
    db: Session,
    file: UploadFile,
    file_path: str,
    *,
    department_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Process one upload file; failures are returned as a failed item, not raised."""
    filename = file.filename or os.path.basename(file_path)
    try:
        validate_upload_file(file)
        result = process_file_upload(db, file, file_path, department_name=department_name)
        return file_upload_item_from_result(filename, result)
    except Exception as exc:
        return file_upload_item_from_error(filename, exc)


def validate_upload_file(file: UploadFile) -> None:
    if not file.filename:
        raise http_error(400, "No file provided")
    if not is_supported_upload(file.filename):
        raise http_error(400, SUPPORTED_FORMATS_MESSAGE)


def validate_csv_columns(
    file_path: str,
) -> Tuple[pd.DataFrame, List[str], List[str], Dict[str, str]]:
    try:
        df = pd.read_csv(file_path, nrows=1)
    except Exception as exc:
        raise http_error(400, "Invalid CSV file", str(exc)) from exc

    df, column_mapping = canonicalize_columns(df)
    found_columns = [str(c) for c in df.columns]
    # Informational only — never reject upload for missing core columns.
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    return df, found_columns, missing_columns, column_mapping


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
    db: Session,
    chunks: Iterable[pd.DataFrame],
    *,
    upload_batch_id: Optional[int] = None,
    source_name: Optional[str] = None,
    department_name: Optional[str] = None,
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
    inserted_records = 0
    skipped_duplicates = 0
    staging_to_add: List[Any] = []
    norm_summary = empty_normalization_summary()
    preview = norm_summary["preview"]
    total_rows = 0
    current_row_number = 2  # header is row 1
    staged_rows = 0
    rejected_rows = 0
    partial_rows = 0
    confidence_summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

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

            # Flexible ingestion: do NOT reject rows just because full_name or dob is missing.
            # Only validate DOB format if present.
            if not _cell_empty(row.get("dob")) and not norm["dob_valid"]:
                row_errors.append(
                    (
                        "INVALID_DOB",
                        "Date of birth must use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD format",
                    )
                )

            # If the row is completely empty, skip it as invalid.
            if all(_cell_empty(row.get(c)) for c in row.index):
                row_errors.append(("EMPTY_ROW", "Row contains no usable data"))

            mobile_key = mobile_lookup_key(normalized.get("mobile"))
            is_duplicate = False
            if mobile_key:
                if mobile_key in existing_mobiles or mobile_key in seen_in_file:
                    is_duplicate = True
                else:
                    existing_citizen = get_citizen_by_mobile(db, mobile_key)
                    if existing_citizen:
                        is_duplicate = True
                        existing_mobiles.add(mobile_key)

            if is_duplicate:
                duplicate_rows += 1
                skipped_duplicates += 1
                duplicate_message = f"Duplicate mobile number: {mobile_key}"
                row_errors.append(("DUPLICATE_MOBILE", duplicate_message))
                _append_error(
                    errors,
                    row_number,
                    "DUPLICATE_MOBILE",
                    duplicate_message,
                )

            extracted_status = "duplicate" if is_duplicate else "staged"
            if row_errors and not is_duplicate:
                invalid_rows += 1
                rejected_rows += 1
                extracted_status = "rejected"
                for error_type, description in row_errors:
                    _append_error(errors, row_number, error_type, description)

            # Import when normalized fields or raw row cells contain usable data.
            has_normalized_data = any(
                v is not None and str(v).strip() != ""
                for v in normalized.values()
            )
            has_raw_data = any(not _cell_empty(row.get(c)) for c in row.index)
            should_import = has_normalized_data or has_raw_data
            if not should_import and extracted_status not in ("rejected", "duplicate"):
                partial_rows += 1
                extracted_status = "partial"

            validation_payload = [
                {"error_type": et, "description": desc} for et, desc in row_errors
            ]
            staging = build_staging_row(
                upload_batch_id=int(upload_batch_id or 0),
                row_number=int(row_number),
                raw_row=row_dict,
                normalized={
                    **normalized,
                    "matching_key": norm.get("matching_key"),
                    "normalized_name": normalized.get("full_name"),
                },
                matching_key=norm.get("matching_key"),
                validation_errors=validation_payload,
                extraction_status=extracted_status,
                source_name=source_name,
                department_name=department_name,
            )
            staging_to_add.append(staging)
            confidence_summary[staging.confidence_level] = confidence_summary.get(
                staging.confidence_level, 0
            ) + 1
            staged_rows += 1

            if mobile_key:
                seen_in_file.add(mobile_key)

            if extracted_status in ("rejected", "duplicate"):
                continue

            if norm["changes"]["name_changed"]:
                norm_summary["names_normalized"] += 1
                _append_preview(
                    preview,
                    row_number,
                    "full_name",
                    originals.get("full_name"),
                    normalized.get("full_name"),
                )
            if norm["changes"]["phone_changed"]:
                norm_summary["phones_normalized"] += 1
                _append_preview(
                    preview,
                    row_number,
                    "mobile",
                    originals.get("mobile"),
                    normalized.get("mobile"),
                )
            if norm["changes"]["dob_changed"]:
                norm_summary["dates_normalized"] += 1
                _append_preview(
                    preview, row_number, "dob", originals.get("dob"), normalized.get("dob")
                )

            if norm.get("matching_key"):
                norm_summary["matching_keys_generated"] += 1

            if should_import:
                citizen = Citizen(
                    full_name=normalized.get("full_name") or "Unknown",
                    mobile=mobile_key,
                    district=normalized.get("district"),
                    village=normalized.get("village"),
                    dob=normalized.get("dob"),
                )
                if safe_insert_citizen(db, citizen):
                    inserted_records += 1
                    valid_rows += 1
                    if mobile_key:
                        existing_mobiles.add(mobile_key)
                else:
                    duplicate_rows += 1
                    skipped_duplicates += 1
                    _append_error(
                        errors,
                        row_number,
                        "DUPLICATE_MOBILE",
                        f"Duplicate mobile number: {mobile_key}",
                    )

            if len(staging_to_add) >= 5000:
                db.add_all(staging_to_add)
                db.commit()
                staging_to_add.clear()

    if staging_to_add:
        db.add_all(staging_to_add)
    db.commit()

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows,
        "duplicate_records": duplicate_rows,
        "inserted_records": inserted_records,
        "skipped_duplicates": skipped_duplicates,
        "errors": errors,
        "rows_imported": inserted_records,
        "rows_skipped": invalid_rows + skipped_duplicates,
        "normalization": norm_summary,
        "staged_rows": staged_rows,
        "rejected_rows": rejected_rows,
        "partial_rows": partial_rows,
        "confidence_summary": confidence_summary,
    }


def save_upload_file(file: UploadFile) -> str:
    ensure_upload_folder()
    safe_name = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


def process_dataframe_upload(
    db: Session,
    *,
    filename: str,
    chunk_iter: Iterable[pd.DataFrame],
    found_columns: Optional[List[str]] = None,
    missing_columns: Optional[List[str]] = None,
    column_mapping: Optional[Dict[str, str]] = None,
    department_name: Optional[str] = None,
    upload_record: Optional[Upload] = None,
) -> dict:
    """
    Core ingestion pipeline: staging + optional citizen import + match candidates.
    Used by single CSV upload and bulk multi-format upload.
    """
    if upload_record is None:
        upload_record = Upload(
            filename=filename,
            uploaded_rows=0,
            uploaded_at=datetime.utcnow(),
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

    missing_value_counts: Dict[str, int] = {c: 0 for c in REQUIRED_COLUMNS}
    preview_rows: Optional[List[Dict[str, Any]]] = None
    analytics_chunk_warnings: List[str] = []

    def _normalized_chunks() -> Iterable[pd.DataFrame]:
        nonlocal preview_rows
        for chunk in chunk_iter:
            if chunk is None or chunk.empty:
                continue
            chunk, _ = canonicalize_columns(chunk)
            sync_result = register_ingested_dataframe(
                chunk,
                upload_id=upload_record.id,
                source_file=filename,
                uploaded_at=upload_record.uploaded_at,
                department_name=department_name,
            )
            if sync_result.get("warning"):
                analytics_chunk_warnings.append(sync_result["warning"])
            if preview_rows is None and not chunk.empty:
                preview_rows = chunk.head(5).to_dict(orient="records")
            for c in REQUIRED_COLUMNS:
                if c in chunk.columns:
                    missing_value_counts[c] += int(chunk[c].apply(_cell_empty).sum())
            yield chunk

    validation = validate_and_import_citizens_iter(
        db,
        _normalized_chunks(),
        upload_batch_id=upload_record.id,
        source_name=filename,
        department_name=department_name,
    )
    rows_imported = validation["rows_imported"]
    upload_record.uploaded_rows = rows_imported
    db.commit()

    summary_warning: Optional[str] = None

    try:
        from app.services.duckdb_analytics_service import sync_upload_summary

        summary_warning = sync_upload_summary(
            upload_id=upload_record.id,
            source_file=filename,
            uploaded_at=upload_record.uploaded_at,
            department_name=department_name,
            validation=validation,
        )

        logger.info(
            "SYNC_UPLOAD_SUMMARY RESULT: upload_id=%s warning=%s",
            upload_record.id,
            summary_warning,
        )

    except Exception as exc:
        summary_warning = f"DuckDB summary sync failed: {exc}"

    analytics_warning = _build_analytics_warning(analytics_chunk_warnings, summary_warning)
    skipped_duplicates = int(validation.get("skipped_duplicates") or 0)
    validation_warning = None
    if skipped_duplicates > 0:
        validation_warning = (
            f"{skipped_duplicates} duplicate mobile number(s) skipped; "
            "upload completed successfully."
        )

    try:
        candidate_stats = generate_candidates_for_upload(db, upload_record.id)
    except Exception:
        candidate_stats = {"created": 0, "skipped": 0}

    total_rows = validation["total_rows"] or 0
    found_columns = found_columns or []
    missing_columns = missing_columns or [c for c in REQUIRED_COLUMNS if c not in found_columns]
    column_mapping = column_mapping or {}

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
        "upload_success": True,
        "success": True,
        "message": "Upload completed with validation results",
        "analytics_warning": analytics_warning,
        "validation_warning": validation_warning,
        "validation_results": {
            "total_rows": validation["total_rows"],
            "valid_rows": validation["valid_rows"],
            "invalid_rows": validation["invalid_rows"],
            "duplicate_rows": validation["duplicate_rows"],
            "duplicate_records": validation.get("duplicate_records", validation["duplicate_rows"]),
            "inserted_records": validation.get("inserted_records", rows_imported),
            "skipped_duplicates": skipped_duplicates,
            "rows_imported": rows_imported,
            "rows_skipped": validation["rows_skipped"],
            "staged_rows": validation.get("staged_rows", 0),
            "rejected_rows": validation.get("rejected_rows", 0),
            "partial_rows": validation.get("partial_rows", 0),
        },
        "file_id": upload_record.id,
        "filename": filename,
        "preview_data": preview_rows or [],
        "rows_imported": rows_imported,
        "rows_skipped": validation["rows_skipped"],
        "total_rows": validation["total_rows"],
        "valid_rows": validation["valid_rows"],
        "invalid_rows": validation["invalid_rows"],
        "duplicate_rows": validation["duplicate_rows"],
        "duplicate_records": validation.get("duplicate_records", validation["duplicate_rows"]),
        "inserted_records": validation.get("inserted_records", rows_imported),
        "skipped_duplicates": skipped_duplicates,
        "errors": validation["errors"],
        "normalization": validation.get("normalization", empty_normalization_summary()),
        "required_columns": REQUIRED_COLUMNS,
        "found_columns": found_columns,
        "missing_columns": missing_columns,
        "column_mapping": column_mapping,
        "missing_values": missing_values,
        "staged_rows": validation.get("staged_rows", 0),
        "confidence_summary": validation.get("confidence_summary", {"HIGH": 0, "MEDIUM": 0, "LOW": 0}),
        "rejected_rows": validation.get("rejected_rows", 0),
        "partial_rows": validation.get("partial_rows", 0),
        "match_candidates": candidate_stats,
    }


def _chunk_dataframe(df: pd.DataFrame) -> Iterable[pd.DataFrame]:
    if len(df) <= UPLOAD_CHUNK_SIZE:
        yield df
        return
    for start in range(0, len(df), UPLOAD_CHUNK_SIZE):
        yield df.iloc[start : start + UPLOAD_CHUNK_SIZE].copy()


def process_file_upload(
    db: Session,
    file: UploadFile,
    file_path: str,
    *,
    department_name: Optional[str] = None,
) -> dict:
    """
    Parse an uploaded file by extension, then run the standard ingestion pipeline.
    CSV keeps chunked streaming; other formats load via file_ingestion_service.
    """
    filename = file.filename or os.path.basename(file_path)
    ext = os.path.splitext(filename.lower())[1]

    if ext == ".csv":
        df, found_columns, missing_columns, column_mapping = validate_csv_columns(file_path)
        chunk_iter = pd.read_csv(file_path, chunksize=UPLOAD_CHUNK_SIZE)
        return process_dataframe_upload(
            db,
            filename=filename,
            chunk_iter=chunk_iter,
            found_columns=found_columns,
            missing_columns=missing_columns,
            column_mapping=column_mapping,
            department_name=department_name,
        )

    try:
        df, file_format, source_type = load_file_as_dataframe(file_path, filename)
    except Exception as exc:
        raise http_error(400, f"Failed to parse file: {filename}", str(exc)) from exc

    if df is None or df.empty:
        raise http_error(400, "No rows found in file", f"File {filename} produced no ingestible rows")

    found_columns = [str(c) for c in df.columns]
    column_mapping = build_column_mapping(list(df.columns))
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    return process_dataframe_upload(
        db,
        filename=filename,
        chunk_iter=_chunk_dataframe(df),
        found_columns=found_columns,
        missing_columns=missing_columns,
        column_mapping=column_mapping,
        department_name=department_name or source_type,
    )


def process_csv_upload(
    db: Session,
    file: UploadFile,
    file_path: str,
) -> dict:
    """Backward-compatible CSV entry point."""
    return process_file_upload(db, file, file_path)
