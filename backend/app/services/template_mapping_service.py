import json
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.exceptions import http_error
from app.models.template_mapping import TemplateMapping
from app.utils.display_validation import validate_display_name


def template_to_dict(record: TemplateMapping) -> dict:
    try:
        mapping = json.loads(record.mapping_json)
    except json.JSONDecodeError:
        mapping = {}
    return {
        "id": record.id,
        "template_name": record.template_name,
        "mapping": mapping,
        "mapping_json": record.mapping_json,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def save_template_mapping(
    db: Session,
    template_name: str,
    mapping: dict,
) -> dict:
    name = validate_display_name(template_name, field_label="Template name")
    if not isinstance(mapping, dict):
        raise http_error(400, "Mapping must be a JSON object")

    record = TemplateMapping(
        template_name=name,
        mapping_json=json.dumps(mapping),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return template_to_dict(record)


def list_template_mappings(db: Session) -> List[dict]:
    records = (
        db.query(TemplateMapping)
        .order_by(desc(TemplateMapping.created_at), desc(TemplateMapping.id))
        .all()
    )
    return [template_to_dict(r) for r in records]


def get_template_mapping_by_id(db: Session, template_id: int) -> Optional[dict]:
    record = db.query(TemplateMapping).filter(TemplateMapping.id == template_id).first()
    if not record:
        return None
    return template_to_dict(record)
