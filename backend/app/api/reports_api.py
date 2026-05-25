from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_REPORTS_READ
from app.services.reports_service import (
    build_excel_export,
    build_pdf_export,
    get_available_reports,
    get_report_data,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Reports"])


@router.get("/reports")
def list_reports(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REPORTS_READ)),
):
    return {
        "success": True,
        "message": "Reports fetched successfully",
        "logged_in_user": current_user.username,
        "reports": get_available_reports(db),
    }


@router.get("/reports/export/pdf")
def export_report_pdf(
    report: str = Query(..., description="Report key: citizen, upload, audit, district"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REPORTS_READ)),
):
    content, filename = build_pdf_export(db, report)
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/export/excel")
def export_report_excel(
    report: str = Query(..., description="Report key: citizen, upload, audit, district"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REPORTS_READ)),
):
    content, filename = build_excel_export(db, report)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_key}")
def view_report(
    report_key: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REPORTS_READ)),
):
    data = get_report_data(db, report_key)
    return {
        "success": True,
        "message": "Report data fetched successfully",
        "logged_in_user": current_user.username,
        **data,
    }
