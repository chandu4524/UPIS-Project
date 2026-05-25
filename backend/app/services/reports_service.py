import io
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.models.audit_log import AuditLog
from app.models.citizen import Citizen
from app.models.upload import Upload
from app.services.citizen_service import citizen_to_dict

MAX_REPORT_ROWS = 1000

REPORT_KEYS = ("citizen", "upload", "audit", "district")

REPORT_META = {
    "citizen": {
        "id": "citizen",
        "name": "Citizen Report",
        "description": "Complete listing of registered citizens in GPIP.",
    },
    "upload": {
        "id": "upload",
        "name": "Upload Report",
        "description": "CSV upload history with row counts and timestamps.",
    },
    "audit": {
        "id": "audit",
        "name": "Audit Report",
        "description": "Officer activity and security audit trail.",
    },
    "district": {
        "id": "district",
        "name": "District Report",
        "description": "Citizen counts grouped by district.",
    },
}


def _validate_report_key(report_key: str) -> str:
    key = (report_key or "").strip().lower()
    if key not in REPORT_KEYS:
        raise http_error(400, "Invalid report type", {"valid_reports": list(REPORT_KEYS)})
    return key


def _count_citizens(db: Session) -> int:
    return db.query(func.count(Citizen.id)).scalar() or 0


def _count_uploads(db: Session) -> int:
    return db.query(func.count(Upload.id)).scalar() or 0


def _count_audits(db: Session) -> int:
    return db.query(func.count(AuditLog.id)).scalar() or 0


def _count_districts(db: Session) -> int:
    return (
        db.query(func.count(func.distinct(Citizen.district)))
        .filter(Citizen.district.isnot(None), Citizen.district != "")
        .scalar()
        or 0
    )


def get_available_reports(db: Session) -> List[dict]:
    counts = {
        "citizen": _count_citizens(db),
        "upload": _count_uploads(db),
        "audit": _count_audits(db),
        "district": _count_districts(db),
    }
    reports = []
    for key in REPORT_KEYS:
        meta = REPORT_META[key].copy()
        meta["record_count"] = counts[key]
        reports.append(meta)
    return reports


def _build_citizen_report(db: Session) -> dict:
    citizens = db.query(Citizen).order_by(Citizen.id).limit(MAX_REPORT_ROWS).all()
    rows = [citizen_to_dict(c) for c in citizens]
    headers = ["id", "full_name", "mobile", "district", "village", "dob"]
    return {
        "report_key": "citizen",
        "title": REPORT_META["citizen"]["name"],
        "headers": headers,
        "rows": [[r.get(h) for h in headers] for r in rows],
        "total": _count_citizens(db),
        "summary": f"{len(rows)} citizen record(s) included (max {MAX_REPORT_ROWS}).",
    }


def _build_upload_report(db: Session) -> dict:
    uploads = (
        db.query(Upload)
        .order_by(Upload.uploaded_at.desc())
        .limit(MAX_REPORT_ROWS)
        .all()
    )
    headers = ["id", "filename", "uploaded_rows", "uploaded_at"]
    rows = [
        [
            u.id,
            u.filename,
            u.uploaded_rows,
            u.uploaded_at.isoformat() if u.uploaded_at else None,
        ]
        for u in uploads
    ]
    return {
        "report_key": "upload",
        "title": REPORT_META["upload"]["name"],
        "headers": headers,
        "rows": rows,
        "total": _count_uploads(db),
        "summary": f"{len(rows)} upload record(s) included.",
    }


def _build_audit_report(db: Session) -> dict:
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(MAX_REPORT_ROWS)
        .all()
    )
    headers = ["id", "username", "action_type", "entity_type", "entity_id", "created_at"]
    rows = [
        [
            e.id,
            e.username,
            e.action_type,
            e.entity_type,
            e.entity_id,
            e.created_at.isoformat() if e.created_at else None,
        ]
        for e in logs
    ]
    return {
        "report_key": "audit",
        "title": REPORT_META["audit"]["name"],
        "headers": headers,
        "rows": rows,
        "total": _count_audits(db),
        "summary": f"{len(rows)} audit event(s) included.",
    }


def _build_district_report(db: Session) -> dict:
    results = (
        db.query(Citizen.district, func.count(Citizen.id).label("citizen_count"))
        .filter(Citizen.district.isnot(None), Citizen.district != "")
        .group_by(Citizen.district)
        .order_by(func.count(Citizen.id).desc())
        .limit(MAX_REPORT_ROWS)
        .all()
    )
    headers = ["district", "citizen_count"]
    rows = [[r[0], r[1]] for r in results]
    return {
        "report_key": "district",
        "title": REPORT_META["district"]["name"],
        "headers": headers,
        "rows": rows,
        "total": len(rows),
        "summary": f"{len(rows)} district(es) with registered citizens.",
    }


def get_report_data(db: Session, report_key: str) -> dict:
    key = _validate_report_key(report_key)
    builders = {
        "citizen": _build_citizen_report,
        "upload": _build_upload_report,
        "audit": _build_audit_report,
        "district": _build_district_report,
    }
    return builders[key](db)


def _report_to_dataframe(report: dict) -> pd.DataFrame:
    return pd.DataFrame(report["rows"], columns=report["headers"])


def build_excel_export(db: Session, report_key: str) -> Tuple[bytes, str]:
    report = get_report_data(db, report_key)
    df = _report_to_dataframe(report)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=report_key[:31], index=False)
    buffer.seek(0)
    filename = f"gpip_{report_key}_report_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return buffer.read(), filename


def build_pdf_export(db: Session, report_key: str) -> Tuple[bytes, str]:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise http_error(
            500,
            "PDF export unavailable — install fpdf on the server",
        ) from exc

    report = get_report_data(db, report_key)
    headers = report["headers"]
    rows = report["rows"]
    landscape = len(headers) > 4

    pdf = FPDF("L" if landscape else "P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Government Person Intelligence Platform", 0, 1)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, report["title"], 0, 1)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, 5, report.get("summary", ""))
    pdf.ln(3)

    col_count = max(len(headers), 1)
    page_w = pdf.w - 20
    col_w = page_w / col_count

    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(11, 37, 69)
    pdf.set_text_color(255, 255, 255)
    for header in headers:
        pdf.cell(col_w, 7, str(header).replace("_", " ")[:28], 1, 0, True)
    pdf.ln()

    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(31, 41, 55)
    for row in rows:
        for cell in row:
            text = "" if cell is None else str(cell)
            pdf.cell(col_w, 6, text[:36], 1)
        pdf.ln()

    raw = pdf.output(dest="S")
    content = raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)
    filename = f"gpip_{report_key}_report_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return content, filename
