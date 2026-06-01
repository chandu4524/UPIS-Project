"""DuckDB analytics engine — hybrid layer alongside the primary SQLAlchemy database."""

from __future__ import annotations

import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from app.core.config import BASE_DIR
from app.core.logging_config import get_logger

logger = get_logger("gpip.duckdb")

DUCKDB_PATH = BASE_DIR / "data" / "gpip_analytics.duckdb"
UPLOADED_DATA_TABLE = "uploaded_data"

_connection: Any = None
_lock = threading.Lock()


def _duckdb():
    import duckdb

    return duckdb


def initialize_duckdb() -> Any:
    """Open (or create) the analytics DuckDB file."""
    global _connection
    with _lock:
        DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _connection is None:
            _connection = _duckdb().connect(str(DUCKDB_PATH))
            logger.info("DuckDB analytics store ready: %s", DUCKDB_PATH)
        return _connection


def get_duckdb_connection() -> Any:
    """Return the shared DuckDB connection, initializing on first use."""
    with _lock:
        if _connection is None:
            return initialize_duckdb()
        return _connection


def close_connection() -> None:
    """Close the shared DuckDB connection."""
    global _connection
    with _lock:
        if _connection is not None:
            try:
                _connection.close()
            except Exception as exc:
                logger.warning("DuckDB close failed: %s", exc)
            finally:
                _connection = None


def _load_dataframe_relation(conn: Any, df: pd.DataFrame, relation: str = "payload") -> None:
    """Load a dataframe into DuckDB via a temp CSV (compatible with older pandas)."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            newline="",
            encoding="utf-8",
        ) as tmp:
            export_df = df.copy()
            if "uploaded_at" in export_df.columns:
                export_df["uploaded_at"] = export_df["uploaded_at"].astype(str)
            export_df.to_csv(tmp, index=False)
            tmp_path = tmp.name
        safe_path = tmp_path.replace("\\", "/").replace("'", "''")
        conn.execute(
            f"CREATE OR REPLACE TEMP TABLE {relation} AS "
            f"SELECT * FROM read_csv_auto('{safe_path}')"
        )
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def register_dataframe(
    name: str,
    df: pd.DataFrame,
    connection: Any = None,
) -> None:
    """Register a pandas DataFrame as a temporary DuckDB view."""
    conn = connection or get_duckdb_connection()
    _load_dataframe_relation(conn, df, relation=name)


def execute_query(
    sql: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
) -> pd.DataFrame:
    """Run a SQL statement and return results as a DataFrame."""
    conn = get_duckdb_connection()
    if params is None:
        return conn.execute(sql).fetchdf()
    return conn.execute(sql, params).fetchdf()


def table_exists(table_name: str) -> bool:
    """Return True if a table exists in the main DuckDB schema."""
    conn = get_duckdb_connection()
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and row[0] > 0)


def _uploaded_data_table_exists(conn: Any) -> bool:
    return table_exists(UPLOADED_DATA_TABLE)


def append_uploaded_data(
    upload_id: int,
    source_file: str,
    df: pd.DataFrame,
    uploaded_at: Optional[datetime] = None,
) -> int:
    """
    Append parsed upload rows to the uploaded_data analytics table.
    Returns number of rows written. Failures should be handled by callers.
    """
    if df is None or df.empty:
        return 0

    conn = get_duckdb_connection()
    payload = df.copy()
    payload["upload_id"] = int(upload_id)
    payload["source_file"] = str(source_file or "")
    payload["uploaded_at"] = (uploaded_at or datetime.utcnow()).isoformat()

    _load_dataframe_relation(conn, payload, relation="payload")

    if not _uploaded_data_table_exists(conn):
        conn.execute(
            f"CREATE TABLE {UPLOADED_DATA_TABLE} AS SELECT * FROM payload"
        )
    else:
        conn.execute(
            f"INSERT INTO {UPLOADED_DATA_TABLE} BY NAME SELECT * FROM payload"
        )

    try:
        conn.execute("DROP TABLE IF EXISTS payload")
    except Exception:
        pass

    return len(payload)


def duckdb_health() -> dict:
    """Lightweight health probe for analytics engine."""
    try:
        conn = get_duckdb_connection()
        conn.execute("SELECT 1").fetchone()
        tables = list_tables()
        return {
            "ready": True,
            "path": str(DUCKDB_PATH),
            "tables": tables,
        }
    except Exception as exc:
        logger.warning("DuckDB health check failed: %s", exc)
        return {
            "ready": False,
            "path": str(DUCKDB_PATH),
            "error": str(exc),
            "tables": [],
        }


def list_tables() -> List[str]:
    """List user tables in the analytics database."""
    conn = get_duckdb_connection()
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).fetchall()
    return [str(r[0]) for r in rows]
