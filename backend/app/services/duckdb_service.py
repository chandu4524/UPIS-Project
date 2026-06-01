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
_lock = threading.RLock()


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


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier for DuckDB."""
    return '"' + str(name).replace('"', '""') + '"'


def _consume_result(result: Any) -> None:
    """Fully consume a DuckDB result so the connection has no open result set."""
    try:
        result.fetchall()
    except Exception:
        pass


def _run_execute(sql: str, params: Optional[Union[List[Any], Dict[str, Any]]] = None) -> None:
    """Run DDL/DML and always consume the result (required for shared connections)."""
    with _lock:
        conn = get_duckdb_connection()
        if params is None:
            _consume_result(conn.execute(sql))
        else:
            _consume_result(conn.execute(sql, params))


def _run_query(
    sql: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
) -> pd.DataFrame:
    """Execute SQL and return a DataFrame; fully consumes the result under lock."""
    with _lock:
        conn = get_duckdb_connection()
        if params is None:
            return conn.execute(sql).fetchdf()
        return conn.execute(sql, params).fetchdf()


def _run_scalar(
    sql: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
) -> Any:
    """Execute SQL and return a single scalar value."""
    with _lock:
        conn = get_duckdb_connection()
        if params is None:
            row = conn.execute(sql).fetchone()
        else:
            row = conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return row[0]


def _run_fetchall(
    sql: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
) -> List[tuple]:
    """Execute SQL and return all rows as tuples."""
    with _lock:
        conn = get_duckdb_connection()
        if params is None:
            return list(conn.execute(sql).fetchall())
        return list(conn.execute(sql, params).fetchall())


def list_table_columns(table_name: str) -> List[str]:
    """Return ordered column names for a persistent table."""
    rows = _run_fetchall(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    )
    return [str(r[0]) for r in rows]


def list_relation_columns(conn: Any, relation: str) -> List[str]:
    """Return column names for a table or temp relation."""
    with _lock:
        df = conn.execute(f"DESCRIBE {_quote_ident(relation)}").fetchdf()
    return [str(c) for c in df["column_name"].tolist()]


def column_exists(table_name: str, column_name: str) -> bool:
    """Return True if a column exists on a persistent table."""
    count = _run_scalar(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = ?
          AND column_name = ?
        """,
        [table_name, column_name],
    )
    return bool(count and int(count) > 0)


def ensure_table_columns(
    table_name: str,
    required_columns: List[str],
    conn: Any = None,
) -> None:
    """Add any missing columns to an existing table (schema evolution)."""
    existing = set(list_table_columns(table_name))
    for col in required_columns:
        if col in existing:
            continue
        sql = (
            f"ALTER TABLE {_quote_ident(table_name)} "
            f"ADD COLUMN {_quote_ident(col)} VARCHAR"
        )
        if conn is not None:
            with _lock:
                _consume_result(conn.execute(sql))
        else:
            _run_execute(sql)
        existing.add(col)


def insert_relation_into_table(
    table_name: str,
    source_relation: str,
    conn: Any = None,
) -> None:
    """
    Schema-safe insert: extend target columns as needed and use NULL for gaps.
    Never references columns that are absent from the target table.
    """
    source_cols = list_relation_columns(conn, source_relation)
    ensure_table_columns(table_name, source_cols, conn)
    target_cols = list_table_columns(table_name)
    source_set = set(source_cols)

    insert_cols = ", ".join(_quote_ident(col) for col in target_cols)
    select_parts = []
    for col in target_cols:
        if col in source_set:
            select_parts.append(_quote_ident(col))
        else:
            select_parts.append("NULL")
    select_sql = ", ".join(select_parts)

    sql = (
        f"INSERT INTO {_quote_ident(table_name)} ({insert_cols}) "
        f"SELECT {select_sql} FROM {_quote_ident(source_relation)}"
    )
    if conn is not None:
        with _lock:
            _consume_result(conn.execute(sql))
    else:
        _run_execute(sql)


def append_dataframe_to_table(
    table_name: str,
    df: pd.DataFrame,
    *,
    relation: str = "payload",
) -> int:
    """Load a dataframe into DuckDB and append rows using schema-safe insert."""
    if df is None or df.empty:
        return 0

    with _lock:
        conn = get_duckdb_connection()
        _load_dataframe_relation(conn, df, relation=relation)

        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        ).fetchone()
        table_present = bool(row and row[0] > 0)

        if not table_present:
            _consume_result(
                conn.execute(
                    f"CREATE TABLE {_quote_ident(table_name)} AS "
                    f"SELECT * FROM {_quote_ident(relation)}"
                )
            )
        else:
            insert_relation_into_table(table_name, relation, conn)

        try:
            _consume_result(conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(relation)}"))
        except Exception:
            pass

    return len(df)


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
        _consume_result(
            conn.execute(
                f"CREATE OR REPLACE TEMP TABLE {relation} AS "
                f"SELECT * FROM read_csv_auto('{safe_path}')"
            )
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
    with _lock:
        conn = connection or get_duckdb_connection()
        _load_dataframe_relation(conn, df, relation=name)


def execute_query(
    sql: str,
    params: Optional[Union[List[Any], Dict[str, Any]]] = None,
) -> pd.DataFrame:
    """Run a SQL statement and return results as a DataFrame."""
    return _run_query(sql, params)


def table_exists(table_name: str) -> bool:
    """Return True if a table exists in the main DuckDB schema."""
    count = _run_scalar(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    )
    return bool(count and int(count) > 0)


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

    payload = df.copy()
    payload["upload_id"] = int(upload_id)
    payload["source_file"] = str(source_file or "")
    payload["uploaded_at"] = (uploaded_at or datetime.utcnow()).isoformat()

    return append_dataframe_to_table(
        UPLOADED_DATA_TABLE,
        payload,
        relation="payload",
    )


def duckdb_health() -> dict:
    """Lightweight health probe for analytics engine."""
    try:
        with _lock:
            conn = get_duckdb_connection()
            conn.execute("SELECT 1 AS ok").fetchdf()
            table_rows = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
                """
            ).fetchall()
        tables = [str(r[0]) for r in table_rows]
        return {
            "ready": True,
            "path": str(DUCKDB_PATH),
            "tables": tables,
        }
    except Exception as exc:
        logger.warning("DuckDB health check failed: %s", exc, exc_info=True)
        return {
            "ready": False,
            "path": str(DUCKDB_PATH),
            "error": str(exc),
            "tables": [],
        }


def list_tables() -> List[str]:
    """List user tables in the analytics database."""
    rows = _run_fetchall(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    )
    return [str(r[0]) for r in rows]
