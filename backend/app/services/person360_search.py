"""360 intelligence search across citizens, staging rows, and source identifiers."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.citizen import Citizen
from app.models.person_staging import PersonStaging
from app.services.citizen_service import mobile_lookup_key
from app.services.header_canonicalization import UNIVERSAL_HEADER_ALIASES, normalize_header
from app.services.intelligence_search_service import (
    MIN_RELEVANCE_SCORE,
    _build_suggestions,
    _normalize_query,
    _score_citizen,
)

IDENTIFIER_CANONICAL_KEYS = tuple(
    k
    for k in (
        "consumer_id",
        "connection_no",
        "customer_id",
        "aadhaar",
        "employee_id",
        "ration_card",
        "account_no",
        "voter_id",
    )
    if k in UNIVERSAL_HEADER_ALIASES
)

DIGITS_RE = re.compile(r"\d{4,}")


def _normalize_name_key(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).strip().lower().split())


def _is_exact_identifier_query(query: str) -> bool:
    q = query.strip()
    if DIGITS_RE.fullmatch(re.sub(r"\D", "", q) if re.sub(r"\D", "", q) else ""):
        return len(re.sub(r"\D", "", q)) >= 4
    return len(q) >= 6 and q.replace(" ", "").isalnum()


def _staging_row_to_candidate(row: PersonStaging, *, score: float, matched_fields: List[str]) -> dict:
    raw = {}
    try:
        raw = json.loads(row.raw_json or "{}")
    except json.JSONDecodeError:
        pass
    source_id = None
    for key in IDENTIFIER_CANONICAL_KEYS:
        val = raw.get(key) or getattr(row, key, None)
        if val:
            source_id = str(val)
            break
    if not source_id and row.matching_key:
        source_id = row.matching_key

    return {
        "id": row.id,
        "citizen_id": None,
        "staging_id": row.id,
        "full_name": row.full_name or raw.get("full_name"),
        "mobile": row.mobile,
        "district": row.district,
        "village": row.village,
        "dob": row.dob,
        "father_name": row.father_name,
        "source_name": row.source_name,
        "department_name": row.department_name,
        "source_id": source_id,
        "upload_batch_id": row.upload_batch_id,
        "relevance_score": round(score, 2),
        "matched_fields": matched_fields,
        "match_type": "staging",
        "highlights": {},
    }


def _search_staging(db: Session, query: str, limit: int) -> List[dict]:
    q = query.strip()
    if not q:
        return []

    mobile_key = mobile_lookup_key(q)
    like = f"%{q}%"
    filters = [
        PersonStaging.full_name.ilike(like),
        PersonStaging.mobile.ilike(like),
        PersonStaging.raw_json.ilike(like),
        PersonStaging.normalized_json.ilike(like),
        PersonStaging.father_name.ilike(like),
        PersonStaging.district.ilike(like),
        PersonStaging.village.ilike(like),
    ]
    if mobile_key:
        filters.append(PersonStaging.mobile == mobile_key)

    rows = (
        db.query(PersonStaging)
        .filter(or_(*filters))
        .order_by(PersonStaging.id.desc())
        .limit(limit * 3)
        .all()
    )

    scored: List[dict] = []
    q_lower = q.lower()
    for row in rows:
        matched: List[str] = []
        best = 0.0

        for field in ("full_name", "mobile", "district", "village", "father_name"):
            val = getattr(row, field, None)
            if not val:
                continue
            text = str(val)
            if q_lower in text.lower():
                score = 100.0
            else:
                score = float(
                    max(
                        fuzz.partial_ratio(q_lower, text.lower()),
                        fuzz.WRatio(q_lower, text.lower()),
                    )
                )
            if score >= MIN_RELEVANCE_SCORE:
                matched.append(field)
                best = max(best, score)

        raw_text = (row.raw_json or "") + (row.normalized_json or "")
        if q_lower in raw_text.lower():
            matched.append("source_record")
            best = max(best, 95.0)

        if matched and best >= MIN_RELEVANCE_SCORE:
            scored.append(_staging_row_to_candidate(row, score=best, matched_fields=matched))

    scored.sort(key=lambda r: (-r["relevance_score"], (r.get("full_name") or "").lower()))
    return scored[:limit]


def _exact_citizen_matches(db: Session, query: str) -> List[Citizen]:
    mobile_key = mobile_lookup_key(query)
    if mobile_key:
        exact = db.query(Citizen).filter(Citizen.mobile == mobile_key).all()
        if exact:
            return exact

    q = query.strip()
    if not q:
        return []

    # Search citizens table for identifier-like exact values
    citizens = db.query(Citizen).all()
    matches: List[Citizen] = []
    q_lower = q.lower()
    for citizen in citizens:
        for attr in ("mobile", "full_name", "district", "village"):
            val = getattr(citizen, attr, None)
            if val and str(val).strip().lower() == q_lower:
                matches.append(citizen)
                break
    return matches


def _detect_ambiguous_groups(results: List[dict]) -> List[dict]:
    """Group citizen results that share a name but differ by mobile/id — do not merge."""
    by_name: Dict[str, List[dict]] = defaultdict(list)
    for row in results:
        if not row.get("id"):
            continue
        name_key = _normalize_name_key(row.get("full_name"))
        if not name_key:
            continue
        by_name[name_key].append(row)

    ambiguous: List[dict] = []
    for name_key, group in by_name.items():
        if len(group) < 2:
            continue
        mobiles = {mobile_lookup_key(r.get("mobile")) or "" for r in group}
        ids = {r.get("id") for r in group}
        if len(mobiles) > 1 or len(ids) > 1:
            ambiguous.append(
                {
                    "normalized_name": name_key,
                    "display_name": group[0].get("full_name") or name_key,
                    "message": "Multiple matching profiles found",
                    "candidates": [
                        {
                            "citizen_id": r.get("id"),
                            "full_name": r.get("full_name"),
                            "mobile": r.get("mobile"),
                            "source_id": r.get("source_id"),
                            "district": r.get("district"),
                            "village": r.get("village"),
                            "relevance_score": r.get("relevance_score"),
                            "matched_fields": r.get("matched_fields", []),
                        }
                        for r in group
                    ],
                }
            )
    return ambiguous


def intelligence_search_360(
    db: Session,
    query: str,
    limit: int = 25,
) -> dict:
    q = _normalize_query(query)
    if not q:
        return {
            "query": "",
            "results": [],
            "staging_results": [],
            "ambiguous_groups": [],
            "suggestions": [],
            "total": 0,
        }

    citizen_scored: List[dict] = []
    seen_citizen_ids: Set[int] = set()

    for citizen in _exact_citizen_matches(db, q):
        if citizen.id in seen_citizen_ids:
            continue
        seen_citizen_ids.add(citizen.id)
        citizen_scored.append(
            {
                "id": citizen.id,
                "citizen_id": citizen.id,
                "staging_id": None,
                "full_name": citizen.full_name,
                "mobile": citizen.mobile,
                "district": citizen.district,
                "village": citizen.village,
                "dob": citizen.dob,
                "father_name": getattr(citizen, "father_name", None),
                "source_id": None,
                "relevance_score": 100.0,
                "matched_fields": ["exact_match"],
                "match_type": "citizen",
                "highlights": {},
            }
        )

    for citizen in db.query(Citizen).all():
        if citizen.id in seen_citizen_ids:
            continue
        row = _score_citizen(citizen, q)
        if row:
            row["citizen_id"] = citizen.id
            row["staging_id"] = None
            row["match_type"] = "citizen"
            row["source_id"] = None
            citizen_scored.append(row)
            seen_citizen_ids.add(citizen.id)

    citizen_scored.sort(
        key=lambda r: (-r["relevance_score"], (r.get("full_name") or "").lower())
    )

    staging_scored = _search_staging(db, q, limit)
    ambiguous_groups = _detect_ambiguous_groups(citizen_scored)

    ambiguous_ids: Set[int] = set()
    for group in ambiguous_groups:
        for candidate in group.get("candidates", []):
            cid = candidate.get("citizen_id")
            if cid:
                ambiguous_ids.add(int(cid))

    # Remove ambiguous duplicates from flat results — user must pick a card
    flat_results = [
        r for r in citizen_scored if r.get("id") not in ambiguous_ids
    ][:limit]

    staging_results = [
        s for s in staging_scored if s.get("staging_id")
    ][: max(0, limit - len(flat_results))]

    suggestions = _build_suggestions(citizen_scored[:50], q)

    return {
        "query": q,
        "results": flat_results,
        "staging_results": staging_results,
        "ambiguous_groups": ambiguous_groups,
        "suggestions": suggestions,
        "total": len(citizen_scored) + len(staging_scored),
        "exact_match": _is_exact_identifier_query(q),
    }
