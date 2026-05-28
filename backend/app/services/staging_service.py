import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.person_staging import PersonStaging

logger = get_logger("gpip.staging")


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({}, ensure_ascii=False)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_confidence_level(
    *,
    name: Optional[str],
    mobile: Optional[str],
    aadhaar: Optional[str],
    dob: Optional[str],
    father_name: Optional[str],
    village: Optional[str],
) -> str:
    has_name = bool(name and str(name).strip())
    has_mobile = bool(mobile and str(mobile).strip())
    has_aadhaar = bool(aadhaar and str(aadhaar).strip())
    has_dob = bool(dob and str(dob).strip())
    has_father = bool(father_name and str(father_name).strip())
    has_village = bool(village and str(village).strip())

    # HIGH confidence
    if (has_name and has_mobile) or (has_name and has_aadhaar) or (has_name and has_dob):
        return "HIGH"
    # MEDIUM confidence
    if (has_name and has_father) or (has_name and has_village) or has_mobile:
        return "MEDIUM"
    return "LOW"


def build_staging_row(
    *,
    upload_batch_id: int,
    row_number: int,
    raw_row: Dict[str, Any],
    normalized: Dict[str, Any],
    matching_key: Optional[str],
    validation_errors: List[Dict[str, Any]],
    extraction_status: str,
    source_name: Optional[str] = None,
    department_name: Optional[str] = None,
) -> PersonStaging:
    full_name = normalized.get("full_name")
    mobile = normalized.get("mobile")
    dob = normalized.get("dob")
    father_name = normalized.get("father_name") or normalized.get("guardian_name")
    spouse_name = normalized.get("spouse_name") or normalized.get("husband_name") or normalized.get("wife_name")
    village = normalized.get("village")
    district = normalized.get("district")

    aadhaar = normalized.get("aadhaar") or normalized.get("aadhaar_no")
    pan = normalized.get("pan") or normalized.get("pan_no")

    confidence = compute_confidence_level(
        name=full_name,
        mobile=mobile,
        aadhaar=aadhaar,
        dob=dob,
        father_name=father_name,
        village=village,
    )

    mobile_hash = _sha256_hex(str(mobile)) if mobile and str(mobile).strip() else None

    return PersonStaging(
        upload_batch_id=int(upload_batch_id),
        row_number=int(row_number),
        raw_json=_safe_json_dumps(raw_row),
        normalized_json=_safe_json_dumps(normalized),
        full_name=full_name,
        normalized_name=normalized.get("normalized_name") or full_name,
        gender=normalized.get("gender"),
        dob=dob,
        father_name=father_name,
        spouse_name=spouse_name,
        mobile=mobile,
        address=normalized.get("address"),
        village=village,
        district=district,
        aadhaar_token=str(aadhaar).strip() if aadhaar else None,
        pan_token=str(pan).strip() if pan else None,
        source_name=source_name,
        department_name=department_name,
        confidence_level=confidence,
        validation_errors=_safe_json_dumps(validation_errors),
        extraction_status=extraction_status,
        matching_key=matching_key,
        mobile_hash=mobile_hash,
    )


def save_staging_rows(db: Session, rows: List[PersonStaging]) -> None:
    if not rows:
        return
    db.add_all(rows)
    db.commit()

