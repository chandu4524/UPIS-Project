"""Health checks and startup diagnostics."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

from app.core.config import (
    APP_ENV,
    DATA_DIR,
    OCR_FOLDER,
    UPLOAD_FOLDER,
    validate_config,
)
from app.database.connection import engine

_STARTUP_DIAGNOSTICS: Dict[str, Any] = {}


def check_ocr_dependencies() -> Dict[str, Any]:
    """Report OCR stack availability without failing startup."""
    status = {
        "pytesseract": False,
        "pdf2image": False,
        "pillow": False,
        "tesseract_binary": False,
        "poppler_available": False,
        "paddleocr": False,
        "ready": False,
        "notes": [],
    }

    try:
        import pytesseract

        status["pytesseract"] = True
        try:
            pytesseract.get_tesseract_version()
            status["tesseract_binary"] = True
        except Exception:
            status["notes"].append("Tesseract binary not found on PATH")
    except ImportError:
        status["notes"].append("pytesseract package not installed")

    try:
        import pdf2image  # noqa: F401

        status["pdf2image"] = True
    except ImportError:
        status["notes"].append("pdf2image package not installed")

    try:
        from PIL import Image  # noqa: F401

        status["pillow"] = True
    except ImportError:
        status["notes"].append("Pillow package not installed")

    if shutil.which("pdftoppm") or shutil.which("pdftocairo"):
        status["poppler_available"] = True
    else:
        status["notes"].append("Poppler utilities not detected on PATH")

    try:
        import paddleocr  # noqa: F401

        status["paddleocr"] = True
    except ImportError:
        pass

    status["ready"] = (
        status["pytesseract"]
        and status["tesseract_binary"]
        and status["pdf2image"]
    )
    return status


def verify_storage_folders() -> Dict[str, Any]:
    """Ensure configured folders exist and are writable."""
    results = {}
    all_ok = True
    for name, path_str in (
        ("data", str(DATA_DIR)),
        ("uploads", UPLOAD_FOLDER),
        ("ocr", OCR_FOLDER),
    ):
        path = Path(path_str)
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".gpip_write_test"
            test_file.write_text("ok", encoding="utf-8")
            if test_file.exists():
                test_file.unlink()
            results[name] = {"path": str(path), "status": "ok"}
        except OSError as exc:
            all_ok = False
            results[name] = {"path": str(path), "status": "error", "detail": str(exc)}
    return {"ok": all_ok, "folders": results}


def check_database_connection() -> Dict[str, Any]:
    """Ping database; return connected or error detail."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "detail": None}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def build_config_validation_summary() -> Dict[str, Any]:
    """Non-fatal configuration warnings for deployment readiness."""
    warnings: List[str] = validate_config()
    return {
        "ok": len(warnings) == 0,
        "warning_count": len(warnings),
        "warnings": warnings,
        "summary": (
            "Configuration OK"
            if not warnings
            else f"{len(warnings)} configuration warning(s) — review before production"
        ),
    }


def _resolve_app_status(db_ok: bool, folders_ok: bool, ocr_ok: bool) -> str:
    if not db_ok:
        return "unhealthy"
    if db_ok and folders_ok and ocr_ok:
        return "healthy"
    return "degraded"


def run_startup_diagnostics() -> Dict[str, Any]:
    """Collect diagnostics at startup (logged, stored for health endpoint)."""
    global _STARTUP_DIAGNOSTICS

    db_result = check_database_connection()
    folders = verify_storage_folders()
    ocr = check_ocr_dependencies()
    config_summary = build_config_validation_summary()

    diagnostics = {
        "environment_mode": APP_ENV,
        "database_connected": db_result["status"] == "connected",
        "database_status": db_result["status"],
        "database_detail": db_result.get("detail"),
        "folders_verified": folders["ok"],
        "folder_checks": folders["folders"],
        "ocr_dependencies": ocr,
        "ocr_ready": ocr.get("ready", False),
        "config_validation": config_summary,
        "config_validation_summary": config_summary["summary"],
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
    _STARTUP_DIAGNOSTICS = diagnostics
    return diagnostics


def get_startup_diagnostics() -> Dict[str, Any]:
    return dict(_STARTUP_DIAGNOSTICS)


def get_health_status(db=None) -> Dict[str, Any]:
    """Build live health payload for GET /api/health."""
    db_result = check_database_connection()
    folders = verify_storage_folders()
    ocr = check_ocr_dependencies()
    startup = get_startup_diagnostics()
    config_summary = build_config_validation_summary()

    db_ok = db_result["status"] == "connected"
    folders_ok = folders["ok"]
    ocr_ok = ocr.get("ready", False)
    app_status = _resolve_app_status(db_ok, folders_ok, ocr_ok)
    generated_at = datetime.utcnow().isoformat() + "Z"

    counts: Dict[str, int] = {}
    if db_ok and db is not None:
        try:
            from app.models.audit_log import AuditLog
            from app.models.citizen import Citizen
            from app.models.entity_review import EntityReview
            from app.models.ocr_document import OcrDocument
            from app.models.upload import Upload

            counts = {
                "citizens": db.query(Citizen).count(),
                "uploads": db.query(Upload).count(),
                "ocr_documents": db.query(OcrDocument).count(),
                "entity_reviews": db.query(EntityReview).count(),
                "audit_logs": db.query(AuditLog).count(),
            }
        except Exception:
            counts = {}

    payload: Dict[str, Any] = {
        "success": app_status != "unhealthy",
        "app_status": app_status,
        "database_status": db_result["status"],
        "environment": APP_ENV,
        "generated_at": generated_at,
    }

    # Backward-compatible extended fields
    payload.update(
        {
            "status": app_status,
            "version": "1.0.0",
            "folders_ok": folders_ok,
            "ocr_ready": ocr_ok,
            "startup_diagnostics": startup or run_startup_diagnostics(),
            "config_validation_summary": config_summary,
            "ocr_dependencies": {
                "ready": ocr_ok,
                "tesseract": ocr.get("tesseract_binary", False),
                "poppler": ocr.get("poppler_available", False),
                "notes": ocr.get("notes", []),
            },
            "folder_checks": folders.get("folders"),
            "record_counts": counts,
        }
    )
    return payload


def log_startup_diagnostics(logger) -> None:
    """Emit startup diagnostics to application logs."""
    diag = run_startup_diagnostics()
    logger.info("Startup diagnostics — environment: %s", diag["environment_mode"])
    logger.info(
        "Database: %s (connected=%s)",
        diag["database_status"],
        diag["database_connected"],
    )
    logger.info("Storage folders verified: %s", diag["folders_verified"])
    for name, info in diag.get("folder_checks", {}).items():
        logger.info("  Folder [%s]: %s — %s", name, info.get("path"), info.get("status"))
    ocr = diag.get("ocr_dependencies", {})
    logger.info(
        "OCR dependencies — ready=%s, tesseract=%s, poppler=%s",
        ocr.get("ready"),
        ocr.get("tesseract_binary"),
        ocr.get("poppler_available"),
    )
    if ocr.get("notes"):
        for note in ocr["notes"]:
            logger.warning("OCR note: %s", note)
    config = diag.get("config_validation", {})
    logger.info("Config validation: %s", config.get("summary", "—"))
    for warning in config.get("warnings", []):
        logger.warning("Config: %s", warning)
