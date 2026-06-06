import math
import re
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.citizen import Citizen
from app.services.normalization_service import normalize_phone

SORT_COLUMNS = {
    "full_name": Citizen.full_name,
    "name": Citizen.full_name,
    "mobile": Citizen.mobile,
    "district": Citizen.district,
}

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
MAX_RELATED_CITIZENS = 5


def _normalize_mobile(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def mobile_lookup_key(value) -> Optional[str]:
    """Canonical mobile key for duplicate detection; None when empty."""
    key = normalize_phone(value)
    return key or None


def get_citizen_by_mobile(db: Session, mobile) -> Optional[Citizen]:
    """Find an existing citizen by normalized mobile number."""
    key = mobile_lookup_key(mobile)
    if not key:
        return None

    match = db.query(Citizen).filter(Citizen.mobile == key).first()
    if match:
        return match

    for citizen in db.query(Citizen).filter(Citizen.mobile.isnot(None), Citizen.mobile != "").all():
        if mobile_lookup_key(citizen.mobile) == key:
            return citizen
    return None


def safe_insert_citizen(db: Session, citizen: Citizen) -> bool:
    """
    Insert one citizen using a savepoint so duplicate mobile never aborts the upload.
    Returns True when inserted, False when skipped as duplicate.
    """
    nested = db.begin_nested()
    try:
        db.add(citizen)
        db.flush()
        nested.commit()
        return True
    except IntegrityError:
        nested.rollback()
        return False


def citizen_to_dict(citizen: Citizen) -> dict:
    data = {
        "id": citizen.id,
        "full_name": citizen.full_name,
        "mobile": citizen.mobile,
        "district": citizen.district,
        "village": citizen.village,
        "dob": citizen.dob,
    }
    for key in ("aadhaar", "aadhar", "pan", "father_name"):
        value = getattr(citizen, key, None)
        if value is not None and str(value).strip():
            data[key] = str(value).strip()
    return data


def citizen_detail_dict(citizen: Citizen) -> dict:
    data = citizen_to_dict(citizen)
    data["created_at"] = (
        citizen.created_at.isoformat() if citizen.created_at else None
    )
    return data


def get_citizen_by_id(db: Session, citizen_id: int) -> Optional[Citizen]:
    return db.query(Citizen).filter(Citizen.id == citizen_id).first()


from app.utils.display_validation import generate_slug


def _graph_slug(value: str) -> str:
    return generate_slug(value) or "unknown"


def build_citizen_relationship_graph(db: Session, citizen_id: int) -> Optional[dict]:
    """Build a relationship graph from citizen attributes and related records."""
    citizen = get_citizen_by_id(db, citizen_id)
    if not citizen:
        return None

    nodes_map: Dict[str, dict] = {}
    links: List[dict] = []
    center_id = f"citizen-{citizen.id}"

    def add_node(
        node_id: str,
        label: str,
        node_type: str,
        is_center: bool = False,
        extra: Optional[dict] = None,
    ) -> None:
        if node_id not in nodes_map:
            node = {
                "id": node_id,
                "label": label,
                "type": node_type,
                "is_center": is_center,
            }
            if extra:
                node.update(extra)
            nodes_map[node_id] = node

    def add_link(source: str, target: str, relationship: str) -> None:
        links.append(
            {"source": source, "target": target, "relationship": relationship}
        )

    add_node(
        center_id,
        citizen.full_name or f"Citizen #{citizen.id}",
        "citizen",
        is_center=True,
        extra={"citizen_id": citizen.id},
    )

    if citizen.mobile:
        mobile_id = f"mobile-{citizen.mobile}"
        add_node(mobile_id, citizen.mobile, "mobile")
        add_link(center_id, mobile_id, "has_mobile")

    if citizen.village:
        village_id = f"village-{_graph_slug(citizen.village)}"
        add_node(village_id, citizen.village, "village")
        add_link(center_id, village_id, "located_in_village")

    if citizen.district:
        district_id = f"district-{_graph_slug(citizen.district)}"
        add_node(district_id, citizen.district, "district")
        add_link(center_id, district_id, "located_in_district")

    related_ids: Set[int] = set()

    if citizen.village:
        same_village = (
            db.query(Citizen)
            .filter(Citizen.village == citizen.village, Citizen.id != citizen.id)
            .limit(MAX_RELATED_CITIZENS)
            .all()
        )
        for related in same_village:
            related_ids.add(related.id)
            rid = f"citizen-{related.id}"
            add_node(
                rid,
                related.full_name or f"Citizen #{related.id}",
                "related_citizen",
                extra={"citizen_id": related.id, "relation": "same_village"},
            )
            add_link(center_id, rid, "same_village")

    if citizen.district:
        same_district = (
            db.query(Citizen)
            .filter(Citizen.district == citizen.district, Citizen.id != citizen.id)
            .limit(MAX_RELATED_CITIZENS)
            .all()
        )
        for related in same_district:
            if related.id in related_ids:
                continue
            related_ids.add(related.id)
            rid = f"citizen-{related.id}"
            add_node(
                rid,
                related.full_name or f"Citizen #{related.id}",
                "related_citizen",
                extra={"citizen_id": related.id, "relation": "same_district"},
            )
            add_link(center_id, rid, "same_district")

    return {
        "center_id": center_id,
        "citizen_id": citizen.id,
        "citizen_name": citizen.full_name,
        "nodes": list(nodes_map.values()),
        "links": links,
    }


def _apply_filters(query, name=None, mobile=None, district=None, village=None):
    if name and name.strip():
        term = f"%{name.strip().lower()}%"
        query = query.filter(func.lower(Citizen.full_name).like(term))
    if mobile and mobile.strip():
        term = f"%{mobile.strip().lower()}%"
        query = query.filter(func.lower(Citizen.mobile).like(term))
    if district and district.strip():
        term = f"%{district.strip().lower()}%"
        query = query.filter(func.lower(Citizen.district).like(term))
    if village and village.strip():
        term = f"%{village.strip().lower()}%"
        query = query.filter(func.lower(Citizen.village).like(term))
    return query


def search_citizens_paginated(
    db: Session,
    name: Optional[str] = None,
    mobile: Optional[str] = None,
    district: Optional[str] = None,
    village: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    sort_by: str = "full_name",
    sort_order: str = "asc",
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    query = db.query(Citizen)
    query = _apply_filters(query, name, mobile, district, village)

    total = query.count()

    sort_col = SORT_COLUMNS.get(sort_by, Citizen.full_name)
    order_fn = desc if sort_order.lower() == "desc" else asc
    query = query.order_by(order_fn(sort_col), desc(Citizen.id))

    offset = (page - 1) * page_size
    citizens = query.offset(offset).limit(page_size).all()
    total_pages = math.ceil(total / page_size) if total else 0

    return {
        "items": [citizen_to_dict(c) for c in citizens],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def search_citizens(
    db: Session,
    name: Optional[str] = None,
    mobile: Optional[str] = None,
    district: Optional[str] = None,
) -> List[dict]:
    result = search_citizens_paginated(
        db,
        name=name,
        mobile=mobile,
        district=district,
        page=1,
        page_size=MAX_PAGE_SIZE,
    )
    return result["items"]


def _load_existing_mobiles(db: Session) -> Set[str]:
    rows = db.query(Citizen.mobile).all()
    keys: Set[str] = set()
    for (mobile,) in rows:
        key = mobile_lookup_key(mobile)
        if key:
            keys.add(key)
    return keys


def import_citizens_from_dataframe(db: Session, df: pd.DataFrame) -> Tuple[int, int]:
    """
    Insert citizens from CSV dataframe.
    Returns (imported_count, skipped_count). Skips empty/duplicate mobiles.
    """
    existing_mobiles = _load_existing_mobiles(db)
    imported = 0
    skipped = 0
    seen_in_file: set = set()

    for _, row in df.iterrows():
        mobile_key = mobile_lookup_key(row.get("mobile"))
        if not mobile_key:
            skipped += 1
            continue
        if mobile_key in existing_mobiles or mobile_key in seen_in_file:
            skipped += 1
            continue

        full_name = str(row.get("full_name", "") or "").strip()
        if not full_name:
            skipped += 1
            continue

        citizen = Citizen(
            full_name=full_name,
            mobile=mobile_key,
            district=str(row.get("district", "") or "").strip() or None,
            village=str(row.get("village", "") or "").strip() or None,
            dob=str(row.get("dob", "") or "").strip() or None,
        )
        if not safe_insert_citizen(db, citizen):
            skipped += 1
            continue

        existing_mobiles.add(mobile_key)
        seen_in_file.add(mobile_key)
        imported += 1

    if imported:
        db.commit()

    return imported, skipped
