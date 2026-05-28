import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.person_relationship import PersonRelationship
from app.models.person_staging import PersonStaging

logger = get_logger("gpip.relationships")


def _safe_json_loads(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _clean(value: Any) -> str:
    s = "" if value is None else str(value).strip()
    return s


def extract_relationships_from_staging(
    staging: PersonStaging,
    *,
    citizen_id: int,
    confidence_score: int,
    source_name: Optional[str],
) -> List[PersonRelationship]:
    norm = _safe_json_loads(staging.normalized_json)
    rels: List[PersonRelationship] = []

    mobile = _clean(norm.get("mobile") or getattr(staging, "mobile", None))
    if mobile:
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="mobile",
                related_entity_value=mobile,
                relationship_type="USES_PHONE",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    address = _clean(norm.get("address") or getattr(staging, "address", None))
    village = _clean(norm.get("village") or getattr(staging, "village", None))
    district = _clean(norm.get("district") or getattr(staging, "district", None))
    if address or village or district:
        value = " | ".join([x for x in [address, village, district] if x])
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="address",
                related_entity_value=value,
                relationship_type="LIVES_AT",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    employer = _clean(norm.get("employer") or norm.get("department"))
    if employer:
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="employer",
                related_entity_value=employer,
                relationship_type="WORKS_FOR",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    scheme = _clean(norm.get("scheme_name"))
    if scheme:
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="scheme",
                related_entity_value=scheme,
                relationship_type="RECEIVES_SCHEME",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    connection_no = _clean(norm.get("connection_no") or norm.get("utility_connection") or norm.get("service_no"))
    if connection_no:
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="utility_connection",
                related_entity_value=connection_no,
                relationship_type="HAS_CONNECTION",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    bank_name = _clean(norm.get("bank_name"))
    if bank_name:
        rels.append(
            PersonRelationship(
                citizen_id=int(citizen_id),
                related_entity_type="bank",
                related_entity_value=bank_name,
                relationship_type="HAS_ACCOUNT",
                confidence_score=int(confidence_score),
                source_name=source_name,
            )
        )

    return rels


def upsert_relationships(
    db: Session,
    relationships: List[PersonRelationship],
) -> int:
    """
    Safe additive insert.
    (No destructive updates; de-dup is intentionally minimal for now.)
    """
    if not relationships:
        return 0
    db.add_all(relationships)
    db.commit()
    return len(relationships)

