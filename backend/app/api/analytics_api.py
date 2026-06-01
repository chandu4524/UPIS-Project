from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_DASHBOARD_ANALYTICS
from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.services.duckdb_analytics_service import (
    get_dashboard_summary,
    get_source_distribution,
    get_upload_trends,
    get_validation_distribution,
)
from app.services.duckdb_service import duckdb_health

logger = get_logger("gpip.analytics_api")

router = APIRouter(prefix="/analytics", tags=["Analytics Dashboard"])


def _ensure_duckdb_ready() -> None:
    status = duckdb_health()
    if not status.get("ready"):
        raise http_error(
            503,
            "DuckDB analytics engine is not available",
            status.get("error"),
        )


@router.get("/dashboard-summary")
def analytics_dashboard_summary(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    summary = get_dashboard_summary()
    return {
        "success": True,
        "message": "Dashboard summary fetched successfully",
        "logged_in_user": current_user.username,
        **summary,
    }


@router.get("/source-distribution")
def analytics_source_distribution(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    """
    Source distribution is isolated from the global DuckDB health gate so a stale
    connection state on this query does not block the endpoint with 503.
    """
    items, warning = get_source_distribution()
    if warning:
        logger.warning("source-distribution returning empty items: %s", warning)
    return {
        "success": True,
        "message": (
            "Source distribution fetched with warnings"
            if warning
            else "Source distribution fetched successfully"
        ),
        "logged_in_user": current_user.username,
        "items": items,
        "warning": warning,
    }


@router.get("/validation-distribution")
def analytics_validation_distribution(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    items = get_validation_distribution()
    return {
        "success": True,
        "message": "Validation distribution fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
    }


@router.get("/upload-trends")
def analytics_upload_trends(
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    items = get_upload_trends()
    return {
        "success": True,
        "message": "Upload trends fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
    }
