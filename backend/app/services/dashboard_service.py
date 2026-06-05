from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.citizen import Citizen
from app.models.upload import Upload
from app.services.data_scope_service import count_duckdb_uploaded_rows, count_person_staging
from app.services.demo_seed_service import DEMO_UPLOAD_FILENAMES


def _real_uploads_query(db: Session):
    return db.query(Upload).filter(~Upload.filename.in_(list(DEMO_UPLOAD_FILENAMES)))


def get_dashboard_stats(db: Session):

    total_citizens = db.query(
        func.count(Citizen.id)
    ).scalar()

    total_staging_rows = count_person_staging(db)
    total_uploaded_data_rows = count_duckdb_uploaded_rows()

    district_count = db.query(
        func.count(
            func.distinct(Citizen.district)
        )
    ).scalar()

    uploaded_files = _real_uploads_query(db).count()

    total_imported_rows = (
        _real_uploads_query(db)
        .with_entities(func.coalesce(func.sum(Upload.uploaded_rows), 0))
        .scalar()
    )

    recent_uploads = (
        _real_uploads_query(db)
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

    intelligence_records = max(
        int(total_staging_rows or 0),
        int(total_uploaded_data_rows or 0),
    )

    return {
        "total_citizens": total_citizens,
        "total_staging_rows": total_staging_rows,
        "total_uploaded_data_rows": total_uploaded_data_rows,
        "intelligence_records": intelligence_records,
        "district_count": district_count,
        "uploaded_files": uploaded_files,
        "total_imported_rows": int(total_imported_rows or 0),
        "last_upload_at": last_upload_at.isoformat() if last_upload_at else None,
        "recent_uploads": recent_upload_list,
    }
