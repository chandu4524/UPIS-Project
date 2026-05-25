from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_DASHBOARD_ANALYTICS, PERM_DASHBOARD_READ
from app.services.analytics_service import get_dashboard_analytics
from app.services.dashboard_service import get_dashboard_stats
from app.utils.dependencies import get_db

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard/analytics")
def dashboard_analytics(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_ANALYTICS)),
):
    analytics = get_dashboard_analytics(db)
    return {
        "success": True,
        "message": "Dashboard analytics fetched successfully",
        "logged_in_user": current_user.username,
        "role": current_user.role,
        "analytics": analytics,
    }


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_DASHBOARD_READ)),
):
    stats = get_dashboard_stats(db)
    return {
        "success": True,
        "message": "Welcome to Secure Dashboard",
        "logged_in_user": current_user.username,
        "role": current_user.role,
        "stats": stats,
    }
