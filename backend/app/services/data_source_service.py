from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.models.data_source import DataSource
from app.utils.display_validation import (
    ensure_unique_slug,
    generate_slug,
    validate_display_name,
)


def data_source_to_dict(source: DataSource) -> dict:
    return {
        "id": source.id,
        "source_name": source.source_name,
        "source_code": source.source_code,
        "description": source.description,
        "is_active": bool(source.is_active),
        "created_at": source.created_at.isoformat() if source.created_at else None,
    }


def list_data_sources(
    db: Session,
    *,
    active_only: bool = False,
) -> List[dict]:
    query = db.query(DataSource).order_by(DataSource.source_name.asc())
    if active_only:
        query = query.filter(DataSource.is_active.is_(True))
    return [data_source_to_dict(row) for row in query.all()]


def get_data_source(db: Session, source_id: int) -> Optional[DataSource]:
    return db.query(DataSource).filter(DataSource.id == int(source_id)).first()


def get_active_data_source(db: Session, source_id: int) -> Optional[DataSource]:
    return (
        db.query(DataSource)
        .filter(DataSource.id == int(source_id), DataSource.is_active.is_(True))
        .first()
    )


def resolve_department_name(db: Session, data_source_id: Optional[int]) -> Optional[str]:
    if not data_source_id:
        return None
    source = get_active_data_source(db, data_source_id)
    if not source:
        raise http_error(400, "Invalid or inactive data source")
    return source.source_code


def _source_code_taken(db: Session, code: str, exclude_id: Optional[int] = None) -> bool:
    existing = db.query(DataSource).filter(DataSource.source_code == code).first()
    return bool(existing and (exclude_id is None or existing.id != exclude_id))


def _generate_source_code(
    db: Session,
    source_name: str,
    *,
    exclude_id: Optional[int] = None,
) -> str:
    base = generate_slug(source_name)
    return ensure_unique_slug(
        base,
        lambda candidate: _source_code_taken(db, candidate, exclude_id=exclude_id),
    )


def _validate_payload(
    *,
    source_name: str,
    db: Session,
    exclude_id: Optional[int] = None,
    existing_code: Optional[str] = None,
    regenerate_code: bool = True,
) -> Dict[str, Any]:
    name = validate_display_name(source_name, field_label="Source name")
    if regenerate_code or not existing_code:
        code = _generate_source_code(db, name, exclude_id=exclude_id)
    else:
        code = existing_code
    return {"source_name": name, "source_code": code}


def create_data_source(
    db: Session,
    *,
    source_name: str,
    description: Optional[str] = None,
    is_active: bool = True,
) -> dict:
    payload = _validate_payload(source_name=source_name, db=db)
    source = DataSource(
        source_name=payload["source_name"],
        source_code=payload["source_code"],
        description=(description or "").strip() or None,
        is_active=bool(is_active),
        created_at=datetime.utcnow(),
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return data_source_to_dict(source)


def update_data_source(
    db: Session,
    source_id: int,
    *,
    source_name: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> dict:
    source = get_data_source(db, source_id)
    if not source:
        raise http_error(404, "Data source not found")

    next_name = source_name if source_name is not None else source.source_name
    regenerate_code = source_name is not None
    payload = _validate_payload(
        source_name=next_name,
        db=db,
        exclude_id=source.id,
        existing_code=source.source_code,
        regenerate_code=regenerate_code,
    )

    source.source_name = payload["source_name"]
    source.source_code = payload["source_code"]
    if description is not None:
        source.description = description.strip() or None
    if is_active is not None:
        source.is_active = bool(is_active)

    db.commit()
    db.refresh(source)
    return data_source_to_dict(source)


def delete_data_source(db: Session, source_id: int) -> None:
    source = get_data_source(db, source_id)
    if not source:
        raise http_error(404, "Data source not found")
    db.delete(source)
    db.commit()
