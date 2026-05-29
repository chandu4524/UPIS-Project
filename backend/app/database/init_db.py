"""Create tables and seed default data."""

from app.auth.auth_handler import hash_password
from app.auth.rbac import ROLE_ADMIN, normalize_role
from app.core.config import (
    DEFAULT_OFFICER_PASSWORD,
    DEFAULT_OFFICER_ROLE,
    DEFAULT_OFFICER_USERNAME,
)
from sqlalchemy import inspect, text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.audit_log import AuditLog  # noqa: F401 — register models
from app.models.entity_review import EntityReview  # noqa: F401
from app.models.template_mapping import TemplateMapping  # noqa: F401
from app.models.citizen import Citizen  # noqa: F401
from app.models.ocr_document import OcrDocument  # noqa: F401
from app.models.match_candidate import MatchCandidate  # noqa: F401
from app.models.person_staging import PersonStaging  # noqa: F401
from app.models.person_source import PersonSource  # noqa: F401
from app.models.person_relationship import PersonRelationship  # noqa: F401
from app.models.upload_batch import UploadBatch, UploadBatchFile  # noqa: F401
from app.models.upload import Upload  # noqa: F401
from app.models.user import User  # noqa: F401


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()
    _seed_default_user()


def _migrate_users_table() -> None:
    """Add is_active / created_at to existing SQLite DBs without breaking data."""
    try:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "is_active" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                    )
                )
            if "created_at" not in columns:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN created_at DATETIME")
                )
                conn.execute(
                    text(
                        "UPDATE users SET created_at = CURRENT_TIMESTAMP "
                        "WHERE created_at IS NULL"
                    )
                )
    except Exception:
        pass


def _seed_default_user() -> None:
    db = SessionLocal()
    try:
        existing = (
            db.query(User)
            .filter(User.username == DEFAULT_OFFICER_USERNAME)
            .first()
        )
        if existing:
            legacy = normalize_role(existing.role)
            changed = False
            if existing.role != legacy:
                existing.role = legacy
                changed = True
            if getattr(existing, "is_active", None) is None:
                existing.is_active = True
                changed = True
            if getattr(existing, "created_at", None) is None:
                from datetime import datetime
                existing.created_at = datetime.utcnow()
                changed = True
            if changed:
                db.commit()
            return

        db.add(
            User(
                username=DEFAULT_OFFICER_USERNAME,
                hashed_password=hash_password(DEFAULT_OFFICER_PASSWORD),
                role=normalize_role(DEFAULT_OFFICER_ROLE or ROLE_ADMIN),
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")
