"""DuckDB-powered upload analytics aggregations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.logging_config import get_logger
from app.services.duckdb_service import (
    UPLOADED_DATA_TABLE,
    append_dataframe_to_table,
    column_exists,
    execute_query,
    table_exists,
)

logger = get_logger("gpip.duckdb_analytics")

UPLOAD_SUMMARIES_TABLE = "upload_summaries"


def sync_upload_summary(
    *,
    upload_id: int,
    source_file: str,
    uploaded_at: datetime,
    department_name: Optional[str],
    validation: Dict[str, Any],
) -> Optional[str]:
    """Persist per-upload validation metrics into DuckDB. Returns warning text on failure."""
    try:
        payload = pd.DataFrame(
            [
                {
                    "upload_id": int(upload_id),
                    "source_file": str(source_file or ""),
                    "uploaded_at": (uploaded_at or datetime.utcnow()).isoformat(),
                    "department_name": (department_name or "GENERAL").strip() or "GENERAL",
                    "total_rows": int(validation.get("total_rows") or 0),
                    "valid_rows": int(validation.get("valid_rows") or 0),
                    "invalid_rows": int(validation.get("invalid_rows") or 0),
                    "duplicate_rows": int(validation.get("duplicate_rows") or 0),
                    "rejected_rows": int(validation.get("rejected_rows") or 0),
                    "partial_rows": int(validation.get("partial_rows") or 0),
                }
            ]
        )
        append_dataframe_to_table(
            UPLOAD_SUMMARIES_TABLE,
            payload,
            relation="summary_payload",
        )
        return None
    except Exception as exc:
        warning = f"DuckDB summary sync failed: {exc}"
        logger.warning("DuckDB upload summary sync failed for upload %s: %s", upload_id, exc)
        return warning


def _empty_summary() -> Dict[str, Any]:
    return {
        "total_uploads": 0,
        "total_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "duplicate_records": 0,
        "success_rate": 0.0,
    }


def get_dashboard_summary() -> Dict[str, Any]:
    if table_exists(UPLOAD_SUMMARIES_TABLE):
        df = execute_query(
            f"""
            SELECT
                COUNT(DISTINCT upload_id) AS total_uploads,
                COALESCE(SUM(total_rows), 0) AS total_records,
                COALESCE(SUM(valid_rows), 0) AS valid_records,
                COALESCE(SUM(invalid_rows), 0) AS invalid_records,
                COALESCE(SUM(duplicate_rows), 0) AS duplicate_records
            FROM {UPLOAD_SUMMARIES_TABLE}
            """
        )
        if not df.empty and int(df.iloc[0]["total_uploads"] or 0) > 0:
            row = df.iloc[0]
            total = int(row["total_records"] or 0)
            valid = int(row["valid_records"] or 0)
            return {
                "total_uploads": int(row["total_uploads"] or 0),
                "total_records": total,
                "valid_records": valid,
                "invalid_records": int(row["invalid_records"] or 0),
                "duplicate_records": int(row["duplicate_records"] or 0),
                "success_rate": round((valid / total * 100.0) if total else 0.0, 2),
            }

    if table_exists(UPLOADED_DATA_TABLE):
        df = execute_query(
            f"""
            SELECT
                COUNT(DISTINCT upload_id) AS total_uploads,
                COUNT(*) AS total_records
            FROM {UPLOADED_DATA_TABLE}
            """
        )
        if not df.empty and int(df.iloc[0]["total_uploads"] or 0) > 0:
            row = df.iloc[0]
            total = int(row["total_records"] or 0)
            return {
                "total_uploads": int(row["total_uploads"] or 0),
                "total_records": total,
                "valid_records": 0,
                "invalid_records": 0,
                "duplicate_records": 0,
                "success_rate": 0.0,
            }

    return _empty_summary()


def get_source_distribution() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Source-wise upload metrics; failures return ([], warning) without affecting DuckDB globally."""
    logger.info("source distribution query started")
    try:
        if table_exists(UPLOAD_SUMMARIES_TABLE):
            df = execute_query(
                f"""
                SELECT
                    COALESCE(department_name, 'GENERAL') AS source,
                    COUNT(DISTINCT upload_id) AS files,
                    COALESCE(SUM(total_rows), 0) AS records,
                    COALESCE(SUM(invalid_rows + duplicate_rows + rejected_rows), 0) AS errors
                FROM {UPLOAD_SUMMARIES_TABLE}
                GROUP BY 1
                ORDER BY records DESC, source ASC
                """
            )
            if not df.empty:
                items = _records_from_df(df)
                logger.info("source distribution query completed (%s rows from summaries)", len(items))
                return items, None

        if table_exists(UPLOADED_DATA_TABLE):
            has_dept = column_exists(UPLOADED_DATA_TABLE, "department_name")
            source_expr = (
                "COALESCE(department_name, 'GENERAL')"
                if has_dept
                else "'GENERAL'"
            )
            df = execute_query(
                f"""
                SELECT
                    {source_expr} AS source,
                    COUNT(DISTINCT upload_id) AS files,
                    COUNT(*) AS records,
                    0 AS errors
                FROM {UPLOADED_DATA_TABLE}
                GROUP BY 1
                ORDER BY records DESC, source ASC
                """
            )
            items = _records_from_df(df)
            logger.info("source distribution query completed (%s rows from uploaded_data)", len(items))
            return items, None

        logger.info("source distribution query completed (no analytics tables)")
        return [], None
    except Exception as exc:
        logger.exception("source distribution query failed")
        return [], f"Source distribution unavailable: {exc}"


def get_validation_distribution() -> List[Dict[str, Any]]:
    if table_exists(UPLOAD_SUMMARIES_TABLE):
        df = execute_query(
            f"""
            SELECT
                COALESCE(SUM(valid_rows), 0) AS valid_records,
                COALESCE(SUM(invalid_rows), 0) AS invalid_records,
                COALESCE(SUM(duplicate_rows), 0) AS duplicate_records
            FROM {UPLOAD_SUMMARIES_TABLE}
            """
        )
        if not df.empty:
            row = df.iloc[0]
            return [
                {"label": "Valid", "count": int(row["valid_records"] or 0)},
                {"label": "Invalid", "count": int(row["invalid_records"] or 0)},
                {"label": "Duplicate", "count": int(row["duplicate_records"] or 0)},
            ]

    return [
        {"label": "Valid", "count": 0},
        {"label": "Invalid", "count": 0},
        {"label": "Duplicate", "count": 0},
    ]


def get_upload_trends() -> List[Dict[str, Any]]:
    if table_exists(UPLOAD_SUMMARIES_TABLE):
        df = execute_query(
            f"""
            SELECT
                CAST(uploaded_at AS DATE) AS date,
                COUNT(DISTINCT upload_id) AS uploads,
                COALESCE(SUM(total_rows), 0) AS records
            FROM {UPLOAD_SUMMARIES_TABLE}
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )
        if not df.empty:
            return _records_from_df(df, date_field="date")

    if table_exists(UPLOADED_DATA_TABLE):
        df = execute_query(
            f"""
            SELECT
                CAST(uploaded_at AS DATE) AS date,
                COUNT(DISTINCT upload_id) AS uploads,
                COUNT(*) AS records
            FROM {UPLOADED_DATA_TABLE}
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )
        return _records_from_df(df, date_field="date")

    return []

def _records_from_df(df: pd.DataFrame, date_field: Optional[str] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        item = {}
        for key, value in record.items():
            if date_field and key == date_field and value is not None:
                item[key] = str(value)
            elif isinstance(value, float) and value.is_integer():
                item[key] = int(value)
            else:
                item[key] = value
        rows.append(item)
    return rows
