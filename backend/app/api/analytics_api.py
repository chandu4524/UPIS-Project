from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_DASHBOARD_ANALYTICS
from app.core.exceptions import http_error
from app.core.logging_config import get_logger
from app.services.analytics_recovery_service import ensure_analytics_synchronized
from app.services.duckdb_analytics_service import (
    get_dashboard_summary,
    get_source_distribution,
    get_upload_trends,
    get_validation_distribution,
)
from app.services.duckdb_service import duckdb_health
from app.utils.dependencies import get_db

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


def _sync_analytics(db: Session) -> None:
    try:
        result = ensure_analytics_synchronized(db)
        if result.get("action") == "rebuilt":
            logger.info("analytics auto-recovery: %s", result)
    except Exception as exc:
        logger.warning("analytics sync check failed (continuing): %s", exc)


@router.get("/dashboard-summary")
def analytics_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    _sync_analytics(db)
    summary = get_dashboard_summary()
    return {
        "success": True,
        "message": "Dashboard summary fetched successfully",
        "logged_in_user": current_user.username,
        **summary,
    }


@router.get("/source-distribution")
def analytics_source_distribution(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _sync_analytics(db)
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
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    _sync_analytics(db)
    items = get_validation_distribution()
    return {
        "success": True,
        "message": "Validation distribution fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
    }


@router.get("/upload-trends")
def analytics_upload_trends(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    _ensure_duckdb_ready()
    _sync_analytics(db)
    items = get_upload_trends()
    return {
        "success": True,
        "message": "Upload trends fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
    }
