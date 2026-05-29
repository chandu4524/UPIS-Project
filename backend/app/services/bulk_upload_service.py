import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.upload_batch import UploadBatch, UploadBatchFile
from app.services.file_ingestion_service import is_supported_upload, load_file_as_dataframe
from app.services.upload_service import ensure_upload_folder, process_dataframe_upload, save_upload_file

logger = get_logger("gpip.bulk_upload")

MAX_BULK_FILES = 60
CHUNK_SIZE = 50000


def _batch_file_to_dict(item: UploadBatchFile) -> dict:
    mapping = {}
    if item.column_mapping_json:
        try:
            mapping = json.loads(item.column_mapping_json)
        except Exception:
            mapping = {}
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "upload_id": item.upload_id,
        "filename": item.filename,
        "file_format": item.file_format,
        "source_type": item.source_type,
        "status": item.status,
        "total_rows": item.total_rows,
        "valid_rows": item.valid_rows,
        "partial_rows": item.partial_rows,
        "rejected_rows": item.rejected_rows,
        "rows_imported": item.rows_imported,
        "error_message": item.error_message,
        "column_mapping": mapping,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _batch_to_dict(batch: UploadBatch, files: Optional[List[UploadBatchFile]] = None) -> dict:
    return {
        "id": batch.id,
        "status": batch.status,
        "total_files": batch.total_files,
        "completed_files": batch.completed_files,
        "failed_files": batch.failed_files,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "files": [_batch_file_to_dict(f) for f in (files or [])],
    }


def create_bulk_batch(db: Session, *, created_by: Optional[str], file_count: int) -> UploadBatch:
    batch = UploadBatch(
        status="processing",
        total_files=file_count,
        completed_files=0,
        failed_files=0,
        created_by=created_by,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def process_single_bulk_file(
    db: Session,
    batch: UploadBatch,
    file: UploadFile,
    file_path: str,
) -> UploadBatchFile:
    """Process one file; failures are captured on the batch file record."""
    filename = file.filename or os.path.basename(file_path)
    item = UploadBatchFile(
        batch_id=batch.id,
        filename=filename,
        file_format="unknown",
        source_type="general",
        status="processing",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    try:
        if not is_supported_upload(filename):
            raise ValueError(
                "Unsupported file type. Allowed: CSV, XLSX, JSON, XML, PDF"
            )

        df, fmt, source_type = load_file_as_dataframe(file_path, filename)
        item.file_format = fmt
        item.source_type = source_type

        if df.empty:
            raise ValueError("No rows found in file")

        found_columns = [str(c) for c in df.columns]
        from app.services.header_canonicalization import CORE_IMPORT_COLUMNS, build_column_mapping

        column_mapping = build_column_mapping(list(df.columns))
        missing_columns = [c for c in CORE_IMPORT_COLUMNS if c not in df.columns]

        def _chunk_iter():
            if len(df) <= CHUNK_SIZE:
                yield df
            else:
                for start in range(0, len(df), CHUNK_SIZE):
                    yield df.iloc[start : start + CHUNK_SIZE].copy()

        result = process_dataframe_upload(
            db,
            filename=filename,
            chunk_iter=_chunk_iter(),
            found_columns=found_columns,
            missing_columns=missing_columns,
            column_mapping=column_mapping,
            department_name=source_type,
        )

        item.upload_id = result.get("file_id")
        item.status = "completed"
        item.total_rows = int(result.get("total_rows") or 0)
        item.valid_rows = int(result.get("valid_rows") or 0)
        item.partial_rows = int(result.get("partial_rows") or 0)
        item.rejected_rows = int(result.get("rejected_rows") or 0)
        item.rows_imported = int(result.get("rows_imported") or 0)
        item.column_mapping_json = json.dumps(column_mapping, ensure_ascii=False)
        item.error_message = None

        batch.completed_files = int(batch.completed_files or 0) + 1
    except Exception as exc:
        logger.exception("Bulk file failed: %s", filename)
        item.status = "failed"
        item.error_message = str(exc)
        batch.failed_files = int(batch.failed_files or 0) + 1

    item.updated_at = datetime.utcnow()
    batch.updated_at = datetime.utcnow()
    if batch.completed_files + batch.failed_files >= batch.total_files:
        batch.status = "completed" if batch.failed_files == 0 else "partial_failure"
    db.commit()
    db.refresh(item)
    return item


def run_bulk_upload(
    db: Session,
    files: List[UploadFile],
    *,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    if not files:
        return {"success": False, "message": "No files provided", "batch": None, "items": []}
    if len(files) > MAX_BULK_FILES:
        return {
            "success": False,
            "message": f"Too many files (max {MAX_BULK_FILES})",
            "batch": None,
            "items": [],
        }

    ensure_upload_folder()
    batch = create_bulk_batch(db, created_by=created_by, file_count=len(files))
    results: List[dict] = []

    for file in files:
        file_path = None
        try:
            file_path = save_upload_file(file)
            item = process_single_bulk_file(db, batch, file, file_path)
            results.append(_batch_file_to_dict(item))
        except Exception as exc:
            logger.exception("Unexpected bulk upload error for %s", file.filename)
            fail = UploadBatchFile(
                batch_id=batch.id,
                filename=file.filename or "unknown",
                file_format="unknown",
                source_type="general",
                status="failed",
                error_message=str(exc),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(fail)
            batch.failed_files = int(batch.failed_files or 0) + 1
            batch.updated_at = datetime.utcnow()
            db.commit()
            results.append(_batch_file_to_dict(fail))
        finally:
            if file_path and os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    db.refresh(batch)
    files_in_batch = (
        db.query(UploadBatchFile)
        .filter(UploadBatchFile.batch_id == batch.id)
        .order_by(UploadBatchFile.id.asc())
        .all()
    )

    return {
        "success": True,
        "message": "Bulk upload completed",
        "batch": _batch_to_dict(batch, files_in_batch),
        "items": results,
        "summary": {
            "total_files": batch.total_files,
            "completed_files": batch.completed_files,
            "failed_files": batch.failed_files,
            "total_rows": sum(int(f.total_rows or 0) for f in files_in_batch),
            "valid_rows": sum(int(f.valid_rows or 0) for f in files_in_batch),
            "partial_rows": sum(int(f.partial_rows or 0) for f in files_in_batch),
            "rejected_rows": sum(int(f.rejected_rows or 0) for f in files_in_batch),
        },
    }


def get_bulk_batch(db: Session, batch_id: int) -> Optional[dict]:
    batch = db.query(UploadBatch).filter(UploadBatch.id == int(batch_id)).first()
    if not batch:
        return None
    files = (
        db.query(UploadBatchFile)
        .filter(UploadBatchFile.batch_id == batch.id)
        .order_by(UploadBatchFile.id.asc())
        .all()
    )
    return _batch_to_dict(batch, files)


def list_bulk_batch_files(
    db: Session,
    batch_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    q = db.query(UploadBatchFile).filter(UploadBatchFile.batch_id == int(batch_id))
    total = q.count()
    rows = (
        q.order_by(UploadBatchFile.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": [_batch_file_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
