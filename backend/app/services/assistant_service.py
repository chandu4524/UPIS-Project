"""Rule-based AI Intelligence Assistant — aggregates GPIP data into conversational answers."""

import re
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.ocr_document import OcrDocument
from app.services.analytics_service import get_dashboard_analytics
from app.services.entity_resolution_service import (
    CATEGORY_CONFIRMED,
    CATEGORY_MANUAL,
    CATEGORY_PROBABLE,
    list_pending_reviews,
)
from app.services.intelligence_search_service import intelligence_search
from app.models.entity_review import EntityReview

SUGGESTED_PROMPTS = [
    "Show top district",
    "Search Chandu",
    "OCR uploads today",
    "Manual review summary",
    "Dashboard analytics summary",
    "Recent audit activity",
]


def _link(label: str, path: str) -> dict:
    return {"label": label, "path": path}


def _action(label: str, path: str, action_type: str = "navigate") -> dict:
    return {"label": label, "type": action_type, "path": path}


def _detect_intent(query: str) -> Tuple[str, Optional[str]]:
    q = query.lower().strip()

    if any(k in q for k in ("manual review", "review queue", "review summary")):
        return "review", None
    if "ocr" in q and any(k in q for k in ("today", "upload", "document", "processed")):
        return "ocr", None
    if "ocr" in q:
        return "ocr", None
    if any(k in q for k in ("audit", "officer activity", "recent action")):
        return "audit", None
    if any(
        k in q
        for k in (
            "top district",
            "dashboard",
            "analytics",
            "district distribution",
            "upload trend",
        )
    ):
        return "dashboard", None

    for pattern in (
        r"(?:search|find|lookup)\s+(.+)",
        r"who\s+is\s+(.+)",
        r"citizen\s+(.+)",
    ):
        match = re.search(pattern, q, re.IGNORECASE)
        if match:
            term = match.group(1).strip(" ?.!")
            if term and len(term) >= 2:
                return "search", term

    if any(k in q for k in ("search", "find", "lookup", "fuzzy")):
        return "search_help", None

    return "help", None


def _handle_dashboard(db: Session) -> dict:
    analytics = get_dashboard_analytics(db)
    district = analytics.get("district", {})
    uploads = analytics.get("uploads", {})
    entity = analytics.get("entity_resolution", {})
    ocr = analytics.get("ocr", {})
    audit = analytics.get("audit", {})

    top = district.get("top_districts") or []
    top_line = (
        f"The top district is **{top[0]['district']}** with {top[0]['count']} citizens."
        if top
        else "No district distribution data is available yet."
    )

    answer = (
        f"**Dashboard analytics summary**\n\n"
        f"{top_line}\n\n"
        f"- Total citizens: {district.get('total_citizens', 0)}\n"
        f"- Uploads: {uploads.get('total_uploads', 0)} files "
        f"({uploads.get('total_imported_rows', 0)} imported rows)\n"
        f"- Entity resolution: {entity.get('confirmed_matches', 0)} confirmed, "
        f"{entity.get('probable_matches', 0)} probable, "
        f"{entity.get('manual_review_count', 0)} manual review\n"
        f"- OCR: {ocr.get('processed_documents', 0)} documents "
        f"(avg confidence {ocr.get('avg_confidence_score', 0)}%)\n"
        f"- Audit: {audit.get('total_actions', 0)} actions across "
        f"{audit.get('officer_activity_count', 0)} officers"
    )

    return {
        "answer": answer,
        "intent": "dashboard",
        "suggested_actions": [
            _action("View full dashboard", "/dashboard"),
            _action("Open reports", "/reports"),
        ],
        "related_links": [
            _link("Dashboard", "/dashboard"),
            _link("Reports", "/reports"),
        ],
    }


def _handle_search(db: Session, term: str) -> dict:
    result = intelligence_search(db, term, limit=5)
    matches = result.get("results") or []
    total = result.get("total", 0)

    if not matches:
        answer = (
            f"No intelligence records matched **{term}**. "
            "Try a partial name, district, or mobile number in Advanced Intelligence Search."
        )
        return {
            "answer": answer,
            "intent": "search",
            "suggested_actions": [
                _action(
                    f"Search “{term}” in Intelligence Search",
                    f"/intelligence-search",
                ),
                _action("Browse citizen records", "/citizens"),
            ],
            "related_links": [
                _link("Intelligence Search", "/intelligence-search"),
                _link("Citizen Records", "/citizens"),
            ],
        }

    lines = [f"Found **{total}** match(es) for **{term}**. Top results:\n"]
    related_links = []
    for idx, row in enumerate(matches[:5], start=1):
        name = row.get("full_name") or "Unknown"
        score = row.get("relevance_score", 0)
        district = row.get("district") or "—"
        lines.append(
            f"{idx}. **{name}** — {district} (relevance {score}%, "
            f"matched: {', '.join(row.get('matched_fields', []))})"
        )
        related_links.append(
            _link(f"Profile: {name}", f"/person-profile/{row['id']}")
        )

    search_path = f"/intelligence-search"
    return {
        "answer": "\n".join(lines),
        "intent": "search",
        "suggested_actions": [
            _action(f"View all matches for “{term}”", search_path),
            _action("Open first profile", f"/person-profile/{matches[0]['id']}"),
        ],
        "related_links": related_links[:5],
    }


def _handle_ocr(db: Session) -> dict:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (
        db.query(func.count(OcrDocument.id))
        .filter(OcrDocument.created_at >= today_start)
        .scalar()
        or 0
    )
    total = db.query(func.count(OcrDocument.id)).scalar() or 0
    avg_conf = db.query(func.avg(OcrDocument.confidence_score)).scalar()
    avg_conf = round(float(avg_conf), 2) if avg_conf is not None else 0.0

    recent = (
        db.query(OcrDocument)
        .order_by(desc(OcrDocument.created_at))
        .limit(3)
        .all()
    )
    recent_lines = []
    for doc in recent:
        recent_lines.append(
            f"- {doc.filename} (confidence {doc.confidence_score:.1f}%)"
        )

    answer = (
        f"**OCR summary**\n\n"
        f"- Processed today: **{today_count}** document(s)\n"
        f"- Total processed: **{total}**\n"
        f"- Average confidence: **{avg_conf}%**\n"
    )
    if recent_lines:
        answer += "\nRecent documents:\n" + "\n".join(recent_lines)

    return {
        "answer": answer,
        "intent": "ocr",
        "suggested_actions": [
            _action("Process new PDF", "/ocr-processing"),
            _action("View OCR history", "/ocr-processing"),
        ],
        "related_links": [_link("OCR Processing", "/ocr-processing")],
    }


def _handle_audit(db: Session) -> dict:
    analytics = get_dashboard_analytics(db)
    audit = analytics.get("audit", {})
    recent = audit.get("recent_actions") or []

    lines = [
        "**Audit activity summary**\n",
        f"- Active officers: **{audit.get('officer_activity_count', 0)}**",
        f"- Total logged actions: **{audit.get('total_actions', 0)}**",
    ]
    if recent:
        lines.append("\nRecent actions:")
        for item in recent[:5]:
            lines.append(
                f"- {item.get('action_type')} by {item.get('username')} "
                f"({item.get('entity_type')})"
            )
    else:
        lines.append("\nNo recent audit entries recorded.")

    return {
        "answer": "\n".join(lines),
        "intent": "audit",
        "suggested_actions": [
            _action("Open audit logs", "/audit-logs"),
        ],
        "related_links": [_link("Audit Logs", "/audit-logs")],
    }


def _handle_review(db: Session) -> dict:
    pending = list_pending_reviews(db)
    confirmed = (
        db.query(func.count(EntityReview.id))
        .filter(EntityReview.category == CATEGORY_CONFIRMED)
        .scalar()
        or 0
    )
    probable = (
        db.query(func.count(EntityReview.id))
        .filter(EntityReview.category == CATEGORY_PROBABLE)
        .scalar()
        or 0
    )
    manual = (
        db.query(func.count(EntityReview.id))
        .filter(EntityReview.category == CATEGORY_MANUAL)
        .scalar()
        or 0
    )

    answer = (
        f"**Manual review summary**\n\n"
        f"- Pending queue: **{len(pending)}** item(s)\n"
        f"- Confirmed matches: **{confirmed}**\n"
        f"- Probable matches: **{probable}**\n"
        f"- Manual review category: **{manual}**\n"
    )
    if pending:
        top = pending[0]
        citizen = top.get("citizen_a") or top.get("citizen_b") or {}
        name = citizen.get("full_name", "Unknown")
        answer += f"\nHighest-priority pending pair involves **{name}** (score {top.get('match_score', 0)})."

    return {
        "answer": answer,
        "intent": "review",
        "suggested_actions": [
            _action("Open manual review queue", "/manual-review"),
        ],
        "related_links": [_link("Manual Review Queue", "/manual-review")],
    }


def _handle_search_help() -> dict:
    answer = (
        "**Search assistance**\n\n"
        "You can ask me to search citizens using natural phrases, for example:\n"
        "- `Search Chandu`\n"
        "- `Find records in Visakhapatnam`\n"
        "- `Lookup 9876543210`\n\n"
        "For advanced fuzzy matching with typo tolerance, use the Intelligence Search module."
    )
    return {
        "answer": answer,
        "intent": "search_help",
        "suggested_actions": [
            _action("Open Intelligence Search", "/intelligence-search"),
            _action("Open Citizen Records", "/citizens"),
        ],
        "related_links": [
            _link("Intelligence Search", "/intelligence-search"),
            _link("Citizen Records", "/citizens"),
        ],
    }


def _handle_help() -> dict:
    prompts = "\n".join(f"- {p}" for p in SUGGESTED_PROMPTS)
    answer = (
        "**GPIP Intelligence Assistant**\n\n"
        "I can summarize dashboard analytics, search citizens, report OCR activity, "
        "audit logs, and manual review status.\n\n"
        f"Try asking:\n{prompts}"
    )
    return {
        "answer": answer,
        "intent": "help",
        "suggested_actions": [
            _action("View dashboard", "/dashboard"),
            _action("Intelligence search", "/intelligence-search"),
        ],
        "related_links": [
            _link("Dashboard", "/dashboard"),
            _link("AI Assistant help", "/ai-assistant"),
        ],
    }


def process_assistant_query(db: Session, query: str, username: str = "") -> dict:
    q = (query or "").strip()
    if not q:
        return {
            "answer": "Please enter a question or choose a suggested prompt below.",
            "intent": "empty",
            "suggested_actions": [],
            "related_links": [],
            "suggested_prompts": SUGGESTED_PROMPTS,
        }

    intent, search_term = _detect_intent(q)

    if intent == "dashboard":
        result = _handle_dashboard(db)
    elif intent == "search" and search_term:
        result = _handle_search(db, search_term)
    elif intent == "ocr":
        result = _handle_ocr(db)
    elif intent == "audit":
        result = _handle_audit(db)
    elif intent == "review":
        result = _handle_review(db)
    elif intent == "search_help":
        result = _handle_search_help()
    else:
        result = _handle_help()

    result["suggested_prompts"] = SUGGESTED_PROMPTS
    result["query"] = q
    if username:
        result["officer"] = username
    return result
