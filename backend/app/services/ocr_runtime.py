"""
OCR runtime detection and configuration for local dev + Render Docker.

Resolves Tesseract and Poppler binaries (Debian: /usr/bin/tesseract, /usr/bin/pdftoppm).
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gpip.ocr.runtime")

_tesseract_cmd_cached: Optional[str] = None
_poppler_path_cached: Optional[str] = None


def resolve_tesseract_cmd() -> Optional[str]:
    """Return path to tesseract executable, or None."""
    global _tesseract_cmd_cached
    if _tesseract_cmd_cached is not None:
        return _tesseract_cmd_cached

    candidates: List[str] = []
    env_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if env_cmd:
        candidates.append(env_cmd)
    candidates.extend(
        [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]
    )
    which_cmd = shutil.which("tesseract")
    if which_cmd:
        candidates.append(which_cmd)

    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            _tesseract_cmd_cached = path
            return path

    _tesseract_cmd_cached = None
    return None


def resolve_poppler_path() -> Optional[str]:
    """
    Return directory containing pdftoppm (for pdf2image poppler_path), or None.
    """
    global _poppler_path_cached
    if _poppler_path_cached is not None:
        return _poppler_path_cached

    env_path = os.getenv("POPPLER_PATH", "").strip()
    if env_path:
        if os.path.isfile(os.path.join(env_path, "pdftoppm")):
            _poppler_path_cached = env_path
            return env_path
        if os.path.isfile(env_path) and os.path.basename(env_path) == "pdftoppm":
            _poppler_path_cached = os.path.dirname(env_path)
            return _poppler_path_cached

    for directory in ("/usr/bin", "/usr/local/bin"):
        if os.path.isfile(os.path.join(directory, "pdftoppm")):
            _poppler_path_cached = directory
            return directory

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        _poppler_path_cached = os.path.dirname(pdftoppm)
        return _poppler_path_cached

    pdftocairo = shutil.which("pdftocairo")
    if pdftocairo:
        _poppler_path_cached = os.path.dirname(pdftocairo)
        return _poppler_path_cached

    _poppler_path_cached = None
    return None


def configure_pytesseract() -> Optional[str]:
    """Point pytesseract at the resolved Tesseract binary."""
    cmd = resolve_tesseract_cmd()
    if not cmd:
        return None
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = cmd
        return cmd
    except ImportError:
        return None


def verify_tesseract() -> bool:
    cmd = configure_pytesseract()
    if not cmd:
        return False
    try:
        import pytesseract

        version = pytesseract.get_tesseract_version()
        logger.info("Tesseract OK path=%s version=%s", cmd, version)
        return True
    except Exception as exc:
        logger.warning("Tesseract verification failed path=%s error=%s", cmd, exc)
        return False


def verify_poppler() -> bool:
    path = resolve_poppler_path()
    if path:
        logger.info("Poppler OK path=%s", path)
        return True
    logger.warning("Poppler utilities not found (pdftoppm/pdftocairo)")
    return False


def check_ocr_dependencies() -> Dict[str, Any]:
    """Full OCR stack check — used by health, status, and upload preflight."""
    status: Dict[str, Any] = {
        "pytesseract": False,
        "pdf2image": False,
        "pillow": False,
        "tesseract_binary": False,
        "poppler_available": False,
        "tesseract_path": None,
        "poppler_path": None,
        "paddleocr": False,
        "ready": False,
        "ocr_ready": False,
        "notes": [],
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        import pytesseract  # noqa: F401

        status["pytesseract"] = True
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

    tesseract_path = resolve_tesseract_cmd()
    status["tesseract_path"] = tesseract_path
    if tesseract_path and status["pytesseract"]:
        status["tesseract_binary"] = verify_tesseract()
    elif not tesseract_path:
        status["notes"].append("Tesseract binary not found on PATH")

    poppler_path = resolve_poppler_path()
    status["poppler_path"] = poppler_path
    status["poppler_available"] = bool(poppler_path)

    if not status["poppler_available"]:
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
        and status["poppler_available"]
        and status["pillow"]
    )
    status["ocr_ready"] = status["ready"]
    return status


def build_ocr_status_payload() -> Dict[str, Any]:
    """Flat payload for GET /api/ocr/status and /api/ocr/health."""
    deps = check_ocr_dependencies()
    return {
        "ocr_ready": deps["ocr_ready"],
        "tesseract_binary": deps["tesseract_binary"],
        "poppler_available": deps["poppler_available"],
        "tesseract_path": deps.get("tesseract_path"),
        "poppler_path": deps.get("poppler_path"),
        "dependencies": deps,
        "config": {
            "OCR_REQUEST_TIMEOUT_SECONDS": os.getenv("OCR_REQUEST_TIMEOUT_SECONDS", "300"),
            "OCR_PDF_DPI": os.getenv("OCR_PDF_DPI", "150"),
            "OCR_MAX_PAGES": os.getenv("OCR_MAX_PAGES", "15"),
            "OCR_MAX_FILE_BYTES": os.getenv("OCR_MAX_FILE_BYTES", str(15 * 1024 * 1024)),
        },
    }


def apply_runtime_configuration() -> Dict[str, Any]:
    """Call at startup; configures pytesseract and logs OCR paths."""
    configure_pytesseract()
    payload = build_ocr_status_payload()
    logger.info(
        "OCR runtime configured ocr_ready=%s tesseract=%s (%s) poppler=%s (%s)",
        payload["ocr_ready"],
        payload["tesseract_binary"],
        payload.get("tesseract_path"),
        payload["poppler_available"],
        payload.get("poppler_path"),
    )
    if not payload["ocr_ready"]:
        for note in payload.get("dependencies", {}).get("notes", []):
            logger.warning("OCR setup: %s", note)
    return payload
