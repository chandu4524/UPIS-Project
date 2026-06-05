"""Rebuild DuckDB analytics from SQLite uploads when summaries are missing or stale."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.person_staging import PersonStaging
from app.models.upload import Upload
from app.services.demo_seed_service import DEMO_UPLOAD_FILENAMES
from app.services.duckdb_analytics_service import (
    UPLOAD_SUMMARIES_TABLE,
    get_dashboard_summary,
    sync_upload_summary,
)
from app.services.duckdb_service import (
    UPLOADED_DATA_TABLE,
    clear_table,
    execute_query,
    initialize_duckdb,
    table_exists,
)

logger = get_logger("gpip.analytics_recovery")


def _real_upload_query(db: Session):
    return db.query(Upload).filter(~Upload.filename.in_(list(DEMO_UPLOAD_FILENAMES)))


def count_real_uploads(db: Session) -> int:
    return _real_upload_query(db).count()


def _staging_metrics(db: Session, upload_id: int) -> Dict[str, int]:
    row = (
        db.query(
            func.count(PersonStaging.id),
            func.sum(case((PersonStaging.extraction_status == "rejected", 1), else_=0)),
            func.sum(case((PersonStaging.extraction_status == "duplicate", 1), else_=0)),
            func.sum(case((PersonStaging.extraction_status == "partial", 1), else_=0)),
        )
        .filter(PersonStaging.upload_batch_id == int(upload_id))
        .one()
    )
    total_rows = int(row[0] or 0)
    rejected = int(row[1] or 0)
    duplicate = int(row[2] or 0)
    partial = int(row[3] or 0)
    return {
        "total_rows": total_rows,
        "rejected_rows": rejected,
        "duplicate_rows": duplicate,
        "partial_rows": partial,
        "invalid_rows": rejected,
        "valid_rows": max(0, total_rows - rejected - duplicate),
    }


def _duckdb_summary_upload_count() -> int:
    if not table_exists(UPLOAD_SUMMARIES_TABLE):
        return 0
    df = execute_query(
        f"SELECT COUNT(DISTINCT upload_id) AS c FROM {UPLOAD_SUMMARIES_TABLE}"
    )
    if df.empty:
        return 0
    return int(df.iloc[0]["c"] or 0)


def ensure_analytics_tables() -> Dict[str, bool]:
    """Ensure DuckDB is initialized; tables are created on first append."""
    initialize_duckdb()
    return {
        "upload_summaries": table_exists(UPLOAD_SUMMARIES_TABLE),
        "uploaded_data": table_exists(UPLOADED_DATA_TABLE),
    }


def rebuild_analytics_from_uploads(db: Session) -> Dict[str, Any]:
    """
    Re-sync upload_summaries from real Upload + PersonStaging records.
    Skips demo seed filenames.
    """
    uploads = _real_upload_query(db).order_by(Upload.id.asc()).all()
    rebuilt = 0
    warnings = 0

    logger.info("analytics rebuild started uploads=%s", len(uploads))

    if table_exists(UPLOAD_SUMMARIES_TABLE):
        clear_table(UPLOAD_SUMMARIES_TABLE)
        logger.info("analytics rebuild cleared existing upload_summaries")

    for upload in uploads:
        metrics = _staging_metrics(db, upload.id)
        if metrics["total_rows"] == 0:
            metrics["total_rows"] = int(upload.uploaded_rows or 0)
            metrics["valid_rows"] = int(upload.uploaded_rows or 0)

        department = None
        dept_row = (
            db.query(PersonStaging.department_name)
            .filter(PersonStaging.upload_batch_id == upload.id)
            .filter(PersonStaging.department_name.isnot(None))
            .first()
        )
        if dept_row and dept_row[0]:
            department = str(dept_row[0])

        validation = {
            **metrics,
            "rows_imported": int(upload.uploaded_rows or 0),
        }
        warning = sync_upload_summary(
            upload_id=upload.id,
            source_file=upload.filename,
            uploaded_at=upload.uploaded_at,
            department_name=department,
            validation=validation,
        )
        if warning:
            warnings += 1
            logger.warning(
                "analytics rebuild sync warning upload_id=%s filename=%s warning=%s",
                upload.id,
                upload.filename,
                warning,
            )
        else:
            rebuilt += 1
            logger.info(
                "analytics rebuild synced upload_id=%s filename=%s rows=%s",
                upload.id,
                upload.filename,
                metrics["total_rows"],
            )

    result = {
        "rebuilt": rebuilt,
        "warnings": warnings,
        "uploads_scanned": len(uploads),
    }
    logger.info("analytics rebuild completed %s", result)
    return result


def ensure_analytics_synchronized(db: Session) -> Dict[str, Any]:
    """
    Auto-recovery: if real uploads exist but DuckDB summaries are empty, rebuild.
    Called before analytics API reads.
    """
    ensure_analytics_tables()
    real_count = count_real_uploads(db)
    summary_count = _duckdb_summary_upload_count()
    summary = get_dashboard_summary()

    if real_count == 0:
        return {
            "action": "none",
            "real_uploads": 0,
            "summary_uploads": summary_count,
        }

    needs_rebuild = (
        summary_count == 0
        or int(summary.get("total_uploads") or 0) == 0
        or summary_count < real_count
    )

    if not needs_rebuild:
        return {
            "action": "ok",
            "real_uploads": real_count,
            "summary_uploads": summary_count,
        }

    logger.warning(
        "analytics mismatch detected real_uploads=%s duckdb_summaries=%s — rebuilding",
        real_count,
        summary_count,
    )
    rebuild_result = rebuild_analytics_from_uploads(db)
    return {
        "action": "rebuilt",
        "real_uploads": real_count,
        "summary_uploads": _duckdb_summary_upload_count(),
        **rebuild_result,
    }

