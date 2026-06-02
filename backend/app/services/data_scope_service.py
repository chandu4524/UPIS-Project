"""Dataset scope counts for dashboards and search diagnostics."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.citizen import Citizen
from app.models.person_staging import PersonStaging
from app.models.upload import Upload


def count_citizens(db: Session) -> int:
    return int(db.query(func.count(Citizen.id)).scalar() or 0)


def count_person_staging(db: Session) -> int:
    return int(db.query(func.count(PersonStaging.id)).scalar() or 0)


def count_upload_files(db: Session) -> int:
    return int(db.query(func.count(Upload.id)).scalar() or 0)


def count_imported_rows(db: Session) -> int:
    return int(db.query(func.coalesce(func.sum(Upload.uploaded_rows), 0)).scalar() or 0)


def count_duckdb_uploaded_rows() -> int:
    try:
        from app.services.duckdb_service import UPLOADED_DATA_TABLE, execute_query, table_exists
    except Exception:
        return 0
    try:
        if not table_exists(UPLOADED_DATA_TABLE):
            return 0
        df = execute_query(f"SELECT COUNT(*) AS c FROM {UPLOADED_DATA_TABLE}")
        if df is None or df.empty:
            return 0
        return int(df.iloc[0]["c"] or 0)
    except Exception:
        return 0


def get_dataset_scope(db: Session) -> Dict[str, int]:
    return {
        "citizens": count_citizens(db),
        "person_staging": count_person_staging(db),
        "uploaded_data": count_duckdb_uploaded_rows(),
        "upload_files": count_upload_files(db),
        "imported_rows": count_imported_rows(db),
    }


def summarize_result_sources(results: list) -> Dict[str, int]:
    counts = {"citizen": 0, "staging": 0, "duckdb": 0}
    for row in results or []:
        source = (row.get("match_type") or row.get("result_source") or "").lower()
        if source in counts:
            counts[source] += 1
        elif row.get("citizen_id"):
            counts["citizen"] += 1
        elif row.get("staging_id"):
            counts["staging"] += 1
    return counts
