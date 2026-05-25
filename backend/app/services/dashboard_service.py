from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.citizen import Citizen
from app.models.upload import Upload


def get_dashboard_stats(db: Session):

    total_citizens = db.query(
        func.count(Citizen.id)
    ).scalar()

    district_count = db.query(
        func.count(
            func.distinct(Citizen.district)
        )
    ).scalar()

    uploaded_files = db.query(
        func.count(Upload.id)
    ).scalar()

    total_imported_rows = db.query(
        func.coalesce(func.sum(Upload.uploaded_rows), 0)
    ).scalar()

    recent_uploads = (
        db.query(Upload)
        .order_by(Upload.uploaded_at.desc())
        .limit(5)
        .all()
    )

    recent_upload_list = []
    last_upload_at = None

    for upload in recent_uploads:
        if last_upload_at is None and upload.uploaded_at:
            last_upload_at = upload.uploaded_at
        recent_upload_list.append({
            "id": upload.id,
            "filename": upload.filename,
            "rows": upload.uploaded_rows,
            "uploaded_at": upload.uploaded_at.isoformat() if upload.uploaded_at else None,
        })

    return {
        "total_citizens": total_citizens,
        "district_count": district_count,
        "uploaded_files": uploaded_files,
        "total_imported_rows": int(total_imported_rows or 0),
        "last_upload_at": last_upload_at.isoformat() if last_upload_at else None,
        "recent_uploads": recent_upload_list,
    }