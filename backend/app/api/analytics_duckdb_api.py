from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_DASHBOARD_ANALYTICS, PERM_DASHBOARD_READ
from app.core.exceptions import http_error
from app.services.duckdb_service import (
    duckdb_health,
    execute_query,
    list_tables,
)

router = APIRouter(prefix="/duckdb", tags=["DuckDB Analytics"])

_FORBIDDEN_SQL = (
    "drop ",
    "delete ",
    "insert ",
    "update ",
    "alter ",
    "create ",
    "attach ",
    "copy ",
    "truncate ",
    "grant ",
    "revoke ",
)


class DuckDBQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="Read-only SELECT query")
    limit: Optional[int] = Field(500, ge=1, le=5000)


def _validate_read_only_sql(sql: str) -> str:
    cleaned = (sql or "").strip()
    if not cleaned:
        raise http_error(400, "SQL query is required")
    lower = cleaned.lower()
    if not lower.startswith("select"):
        raise http_error(400, "Only SELECT queries are allowed")
    if ";" in cleaned.rstrip(";"):
        raise http_error(400, "Multiple SQL statements are not allowed")
    if any(token in lower for token in _FORBIDDEN_SQL):
        raise http_error(400, "Only read-only SELECT queries are allowed")
    return cleaned.rstrip(";")


@router.get("/health")
def duckdb_health_route(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_READ)),
):
    status = duckdb_health()
    return {
        "success": True,
        "message": "DuckDB analytics health fetched successfully",
        "logged_in_user": current_user.username,
        **status,
    }


@router.get("/tables")
def duckdb_tables_route(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_READ)),
):
    tables = list_tables()
    return {
        "success": True,
        "message": "DuckDB tables fetched successfully",
        "logged_in_user": current_user.username,
        "tables": tables,
        "count": len(tables),
    }


@router.post("/query")
def duckdb_query_route(
    body: DuckDBQueryRequest,
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    sql = _validate_read_only_sql(body.sql)
    try:
        df = execute_query(sql)
        if body.limit and len(df) > body.limit:
            df = df.head(body.limit)
        rows: List[dict] = df.to_dict(orient="records")
        columns: List[str] = [str(c) for c in df.columns]
    except Exception as exc:
        raise http_error(400, "DuckDB query failed", str(exc)) from exc

    return {
        "success": True,
        "message": "Query executed successfully",
        "logged_in_user": current_user.username,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
    }
