from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_AUDIT_READ
from app.services.audit_service import list_audit_logs_paginated
from app.utils.dependencies import get_db

router = APIRouter(tags=["Audit Logs"])


@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_AUDIT_READ)),
):
    result = list_audit_logs_paginated(db, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Audit logs fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }
