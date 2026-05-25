"""Fuzzy intelligence search across citizen records using rapidfuzz."""

from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz
from rapidfuzz.fuzz import partial_ratio_alignment
from sqlalchemy.orm import Session

from app.models.citizen import Citizen

SEARCH_FIELDS: Tuple[Tuple[str, float], ...] = (
    ("full_name", 1.0),
    ("mobile", 1.0),
    ("district", 0.95),
    ("village", 0.9),
    ("father_name", 0.85),
)

MIN_RELEVANCE_SCORE = 52
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
MAX_SUGGESTIONS = 8


def _normalize_query(query: str) -> str:
    return " ".join((query or "").strip().split())


def _field_value(citizen: Citizen, field: str) -> str:
    if field == "father_name":
        raw = getattr(citizen, "father_name", None)
    else:
        raw = getattr(citizen, field, None)
    if raw is None:
        return ""
    return str(raw).strip()


def _score_field(query: str, value: str) -> float:
    if not value:
        return 0.0
    q = query.lower()
    v = value.lower()
    if q in v:
        return 100.0
    return float(
        max(
            fuzz.partial_ratio(q, v),
            fuzz.ratio(q, v),
            fuzz.token_set_ratio(q, v),
            fuzz.WRatio(q, v),
        )
    )


def _match_span(query: str, value: str) -> Optional[Tuple[int, int]]:
    if not value or not query:
        return None
    try:
        align = partial_ratio_alignment(query, value, score_cutoff=MIN_RELEVANCE_SCORE)
        if align and align.dest_start is not None and align.dest_end is not None:
            return (align.dest_start, align.dest_end)
    except (TypeError, ValueError):
        pass
    idx = value.lower().find(query.lower())
    if idx >= 0:
        return (idx, idx + len(query))
    return None


def _build_highlight(value: str, query: str, matched: bool) -> dict:
    if not value:
        return {"text": "", "spans": []}
    if not matched:
        return {"text": value, "spans": []}
    span = _match_span(query, value)
    if span:
        return {"text": value, "spans": [list(span)]}
    return {"text": value, "spans": []}


def _score_citizen(citizen: Citizen, query: str) -> Optional[dict]:
    matched_fields: List[str] = []
    field_scores: Dict[str, float] = {}
    best_weighted = 0.0

    for field, weight in SEARCH_FIELDS:
        value = _field_value(citizen, field)
        if not value:
            continue
        raw_score = _score_field(query, value)
        weighted = raw_score * weight
        if raw_score >= MIN_RELEVANCE_SCORE:
            matched_fields.append(field)
            field_scores[field] = round(raw_score, 2)
        best_weighted = max(best_weighted, weighted)

    if not matched_fields or best_weighted < MIN_RELEVANCE_SCORE:
        return None

    highlights = {}
    for field in matched_fields:
        value = _field_value(citizen, field)
        highlights[field] = _build_highlight(value, query, True)

    return {
        "id": citizen.id,
        "full_name": citizen.full_name,
        "mobile": citizen.mobile,
        "district": citizen.district,
        "village": citizen.village,
        "dob": citizen.dob,
        "father_name": _field_value(citizen, "father_name") or None,
        "relevance_score": round(best_weighted, 2),
        "matched_fields": matched_fields,
        "field_scores": field_scores,
        "highlights": highlights,
    }


def _build_suggestions(results: List[dict], query: str) -> List[str]:
    seen = set()
    suggestions: List[str] = []
    q_lower = query.lower()

    for row in results:
        for field in row.get("matched_fields", []):
            text = (row.get(field) or "").strip()
            if not text or text.lower() in seen:
                continue
            if q_lower in text.lower() or len(suggestions) < MAX_SUGGESTIONS:
                seen.add(text.lower())
                suggestions.append(text)
                if len(suggestions) >= MAX_SUGGESTIONS:
                    return suggestions

    for row in results:
        for field in ("full_name", "district", "village"):
            text = (row.get(field) or "").strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                suggestions.append(text)
                if len(suggestions) >= MAX_SUGGESTIONS:
                    break
        if len(suggestions) >= MAX_SUGGESTIONS:
            break

    return suggestions


def intelligence_search(
    db: Session,
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    q = _normalize_query(query)
    limit = min(max(1, limit), MAX_LIMIT)

    if not q:
        return {
            "query": "",
            "results": [],
            "suggestions": [],
            "total": 0,
        }

    citizens = db.query(Citizen).all()
    scored: List[dict] = []

    for citizen in citizens:
        row = _score_citizen(citizen, q)
        if row:
            scored.append(row)

    scored.sort(
        key=lambda r: (-r["relevance_score"], (r.get("full_name") or "").lower())
    )
    results = scored[:limit]
    suggestions = _build_suggestions(scored[:50], q)

    return {
        "query": q,
        "results": results,
        "suggestions": suggestions,
        "total": len(scored),
    }
