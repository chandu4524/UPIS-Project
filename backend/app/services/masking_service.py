"""Field-level masking for sensitive citizen data."""

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.auth.rbac import PERM_VIEW_SENSITIVE_FIELDS, has_permission

SENSITIVE_KEYS = frozenset({"mobile", "aadhaar", "aadhar", "pan"})


def mask_mobile(mobile: Optional[str]) -> str:
    """
    Mask mobile numbers: 9876543210 -> 98765xxxxx
    Keeps first 5 digits visible when possible.
    """
    if mobile is None:
        return ""
    text = str(mobile).strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if not digits:
        return mask_sensitive_text(text)
    if len(digits) <= 5:
        return "x" * len(digits)
    return digits[:5] + ("x" * (len(digits) - 5))


def mask_sensitive_text(value: Optional[str]) -> str:
    """Mask generic sensitive identifiers (Aadhaar, PAN, etc.)."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "x" * len(text)
    return text[:2] + ("x" * (len(text) - 4)) + text[-2:]


def can_view_sensitive_fields(role: str) -> bool:
    return has_permission(role, PERM_VIEW_SENSITIVE_FIELDS)


def _mask_value(key: str, value: Any) -> Any:
    if value is None or value == "":
        return value
    if key == "mobile":
        return mask_mobile(value)
    if key in ("aadhaar", "aadhar", "pan"):
        return mask_sensitive_text(value)
    return mask_sensitive_text(value)


def apply_citizen_masking(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of citizen dict with sensitive fields masked."""
    if not data:
        return data
    result = deepcopy(data)
    for key in SENSITIVE_KEYS:
        if key in result and result[key]:
            result[key] = _mask_value(key, result[key])
    highlights = result.get("highlights")
    if isinstance(highlights, dict):
        masked_highlights = {}
        for field, hl in highlights.items():
            if field in SENSITIVE_KEYS and isinstance(hl, dict):
                text = hl.get("text", "")
                masked_highlights[field] = {
                    "text": _mask_value(field, text),
                    "spans": [],
                }
            else:
                masked_highlights[field] = hl
        result["highlights"] = masked_highlights
    return result


def apply_citizen_list_masking(items: List[dict]) -> List[dict]:
    return [apply_citizen_masking(item) for item in items]


def mask_relationship_graph(graph: Optional[dict]) -> Optional[dict]:
    """Mask mobile labels on relationship graph nodes."""
    if not graph:
        return graph
    result = deepcopy(graph)
    for node in result.get("nodes", []):
        if node.get("type") == "mobile" and node.get("label"):
            node["label"] = mask_mobile(node["label"])
    return result


def sensitive_access_meta(role: str) -> Dict[str, bool]:
    can_view = can_view_sensitive_fields(role)
    return {
        "can_view_sensitive_fields": can_view,
        "sensitive_fields_masked": not can_view,
    }
