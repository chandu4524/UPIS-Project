"""
Human-readable display name validation and slug generation for GPIP.

User-facing forms accept normal labels (spaces, punctuation). Internal identifiers
(source_code, graph slugs, etc.) are generated automatically from display names.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from app.core.exceptions import http_error

DISPLAY_NAME_MAX_LENGTH = 255
SLUG_MAX_LENGTH = 64

# Letters, numbers, spaces, and: - _ & ( ) . /
DISPLAY_NAME_PATTERN = re.compile(r"^[\w\s\-_&()./]+$", re.UNICODE)

DISPLAY_NAME_ALLOWED_MESSAGE = (
    "Use letters, numbers, spaces, and common punctuation ( - _ & ( ) . / ) only."
)


def normalize_display_name(value: str) -> str:
    """Trim and collapse internal whitespace."""
    text = (value or "").strip()
    return re.sub(r"\s+", " ", text)


def validate_display_name(
    value: str,
    *,
    field_label: str = "Name",
    max_length: int = DISPLAY_NAME_MAX_LENGTH,
    required: bool = True,
) -> str:
    """
    Validate a user-facing display name. Returns normalized name or raises HTTP 400.
    """
    name = normalize_display_name(value)
    if not name:
        if required:
            raise http_error(400, f"{field_label} is required.")
        return ""

    if len(name) > max_length:
        raise http_error(
            400,
            f"{field_label} must be {max_length} characters or fewer.",
        )

    if not DISPLAY_NAME_PATTERN.match(name):
        raise http_error(400, f"{field_label}: {DISPLAY_NAME_ALLOWED_MESSAGE}")

    return name


def generate_slug(value: str, *, max_length: int = SLUG_MAX_LENGTH) -> str:
    """Build a lowercase machine-readable slug from a display name."""
    text = normalize_display_name(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "item"
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "item"


def ensure_unique_slug(
    base_slug: str,
    is_taken: Callable[[str], bool],
    *,
    max_length: int = SLUG_MAX_LENGTH,
) -> str:
    """Return base_slug or append -2, -3, … until is_taken returns False."""
    candidate = base_slug[:max_length].rstrip("-") or "item"
    if not is_taken(candidate):
        return candidate

    n = 2
    while n < 10_000:
        suffix = f"-{n}"
        trimmed = base_slug[: max_length - len(suffix)].rstrip("-") or "item"
        candidate = f"{trimmed}{suffix}"
        if not is_taken(candidate):
            return candidate
        n += 1

    raise http_error(409, "Could not generate a unique identifier. Try a different name.")
