"""Application configuration loaded from environment variables (.env supported)."""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# backend/ directory (parent of app/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Load .env from backend root (safe if missing)
_env_path = BASE_DIR / ".env"
if _env_path.is_file():
    load_dotenv(_env_path)
else:
    load_dotenv()

_DEFAULT_SECRET_KEY = "supersecretkey"
_DEFAULT_DB_PATH = DATA_DIR / "upis.db"
_DEFAULT_UPLOAD_FOLDER = BASE_DIR / "uploads"
_DEFAULT_OCR_FOLDER = BASE_DIR / "ocr_uploads"


def _resolve_folder_path(value: str, default: Path) -> str:
    if not value or not str(value).strip():
        path = default
    else:
        path = Path(str(value).strip())
        if not path.is_absolute():
            path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))

# Database
DATA_DIR.mkdir(parents=True, exist_ok=True)
_db_url_env = os.getenv("DATABASE_URL", "").strip()
if _db_url_env:
    DATABASE_URL = _db_url_env
else:
    DATABASE_URL = f"sqlite:///{_DEFAULT_DB_PATH.as_posix()}"

DATABASE_PATH = _DEFAULT_DB_PATH

# Security / JWT
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY).strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", os.getenv("JWT_EXPIRY_MINUTES", "60"))
)

# Storage paths
UPLOAD_FOLDER = _resolve_folder_path(
    os.getenv("UPLOAD_FOLDER", ""),
    _DEFAULT_UPLOAD_FOLDER,
)
OCR_FOLDER = _resolve_folder_path(
    os.getenv("OCR_FOLDER", ""),
    _DEFAULT_OCR_FOLDER,
)

# Default officer account (created on first run if missing)
DEFAULT_OFFICER_USERNAME = os.getenv("DEFAULT_OFFICER_USERNAME", "chandu")
DEFAULT_OFFICER_PASSWORD = os.getenv("DEFAULT_OFFICER_PASSWORD", "Chandu@24")
DEFAULT_OFFICER_ROLE = os.getenv("DEFAULT_OFFICER_ROLE", "admin")


def _mask_database_url(url: str) -> str:
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host_part = rest.rsplit("@", 1)
            return f"{scheme}://***@{host_part}"
    return url


def validate_config() -> List[str]:
    """Return configuration warnings (non-fatal). Safe defaults apply for local dev."""
    issues: List[str] = []

    if not os.getenv("DATABASE_URL"):
        issues.append(
            "DATABASE_URL not set — using local SQLite default "
            f"({DATABASE_PATH})."
        )

    if not os.getenv("SECRET_KEY"):
        issues.append(
            "SECRET_KEY not set — using development default. "
            "Set a strong SECRET_KEY before production deployment."
        )
    elif SECRET_KEY == _DEFAULT_SECRET_KEY and APP_ENV in ("production", "prod"):
        issues.append(
            "SECRET_KEY is still the default value in production — "
            "set a unique SECRET_KEY immediately."
        )

    if not os.getenv("UPLOAD_FOLDER"):
        issues.append(f"UPLOAD_FOLDER not set — using default ({UPLOAD_FOLDER}).")

    if not os.getenv("OCR_FOLDER"):
        issues.append(f"OCR_FOLDER not set — using default ({OCR_FOLDER}).")

    if not os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES") and not os.getenv(
        "JWT_EXPIRY_MINUTES"
    ):
        issues.append(
            f"JWT expiry not set — using default {ACCESS_TOKEN_EXPIRE_MINUTES} minutes."
        )

    return issues


def log_config_summary(logger) -> None:
    """Emit startup configuration summary (secrets masked)."""
    logger.info("GPIP configuration loaded (APP_ENV=%s)", APP_ENV)
    logger.info("Database URL: %s", _mask_database_url(DATABASE_URL))
    logger.info("Upload folder: %s", UPLOAD_FOLDER)
    logger.info("OCR folder: %s", OCR_FOLDER)
    logger.info("JWT expiry: %s minutes", ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info("Log level: %s", LOG_LEVEL)

    for message in validate_config():
        logger.warning("Config: %s", message)


def ensure_runtime_directories() -> None:
    """Ensure data and upload directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(OCR_FOLDER).mkdir(parents=True, exist_ok=True)
