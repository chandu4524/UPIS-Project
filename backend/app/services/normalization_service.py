import hashlib
import re
from typing import Any, Dict, Optional, Tuple

import pandas as pd

STANDARD_DOB_FORMAT = "%d-%m-%Y"
MAX_PREVIEW_ITEMS = 40

# Allow human-readable text: letters, numbers, spaces, - _ & ( ) . / and apostrophes in names.
_INVALID_TEXT_RE = re.compile(r"[^\w\s\-_&()./']", re.UNICODE)


def _raw_string(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def normalize_name(value) -> str:
    text = _raw_string(value)
    if not text:
        return ""
    text = _INVALID_TEXT_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return " ".join(word.capitalize() for word in text.split(" "))


def normalize_phone(value) -> str:
    text = _raw_string(value)
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits


def normalize_dob(value) -> Tuple[str, bool]:
    text = _raw_string(value)
    if not text:
        return "", False

    dmy = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", text)
    if dmy:
        day, month, year = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
        return f"{day:02d}-{month:02d}-{year}", True

    ymd = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)
    if ymd:
        year, month, day = int(ymd.group(1)), int(ymd.group(2)), int(ymd.group(3))
        return f"{day:02d}-{month:02d}-{year}", True

    return text, False


def normalize_text(value) -> str:
    text = _raw_string(value)
    if not text:
        return ""
    text = _INVALID_TEXT_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return " ".join(word.capitalize() for word in text.split(" "))


def generate_matching_key(full_name: str, mobile: str, dob: str) -> str:
    payload = f"{full_name.strip().lower()}|{mobile.strip()}|{dob.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def normalize_citizen_row(row: dict) -> Dict[str, Any]:
    """Normalize a citizen row and return values plus change tracking."""
    originals = {
        "full_name": _raw_string(row.get("full_name")),
        "mobile": _raw_string(row.get("mobile")),
        "dob": _raw_string(row.get("dob")),
        "district": _raw_string(row.get("district")),
        "village": _raw_string(row.get("village")),
    }

    normalized_dob, dob_ok = normalize_dob(originals["dob"])
    normalized = {
        "full_name": normalize_name(originals["full_name"]),
        "mobile": normalize_phone(originals["mobile"]),
        "dob": normalized_dob if dob_ok else originals["dob"],
        "district": normalize_text(originals["district"]) or None,
        "village": normalize_text(originals["village"]) or None,
    }

    changes = {
        "name_changed": normalized["full_name"] != originals["full_name"]
        and bool(originals["full_name"]),
        "phone_changed": normalized["mobile"] != originals["mobile"]
        and bool(originals["mobile"]),
        "dob_changed": normalized["dob"] != originals["dob"] and bool(originals["dob"]),
    }

    matching_key = ""
    if normalized["full_name"] and normalized["mobile"] and normalized["dob"] and dob_ok:
        matching_key = generate_matching_key(
            normalized["full_name"],
            normalized["mobile"],
            normalized["dob"],
        )

    return {
        "originals": originals,
        "normalized": normalized,
        "dob_valid": dob_ok,
        "changes": changes,
        "matching_key": matching_key,
    }


def _append_preview(
    preview: list,
    row_number: int,
    field: str,
    original: str,
    normalized: str,
) -> None:
    if len(preview) >= MAX_PREVIEW_ITEMS:
        return
    if original == normalized:
        return
    preview.append(
        {
            "row_number": row_number,
            "field": field,
            "original": original,
            "normalized": normalized,
        }
    )


def empty_normalization_summary() -> dict:
    return {
        "names_normalized": 0,
        "phones_normalized": 0,
        "dates_normalized": 0,
        "matching_keys_generated": 0,
        "preview": [],
    }
