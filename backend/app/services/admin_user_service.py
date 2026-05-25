"""Admin user management service."""

import math
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.auth_handler import hash_password
from app.auth.rbac import ALL_ROLES, ROLE_LABELS, normalize_role, role_label
from app.core.exceptions import http_error
from app.models.user import User
from app.schemas.user_schema import AdminUserCreate, AdminUserUpdate

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def user_to_admin_dict(user: User) -> dict:
    role = normalize_role(user.role)
    is_active = bool(getattr(user, "is_active", True))
    created = getattr(user, "created_at", None)
    return {
        "id": user.id,
        "username": user.username,
        "role": role,
        "role_label": role_label(role),
        "is_active": is_active,
        "active_status": "active" if is_active else "inactive",
        "created_at": created.isoformat() if created else None,
    }


def list_users_paginated(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    query = db.query(User)
    total = query.count()
    users = (
        query.order_by(desc(User.created_at), desc(User.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = math.ceil(total / page_size) if total else 0

    return {
        "items": [user_to_admin_dict(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_assignable_roles() -> List[dict]:
    return [
        {"value": role, "label": ROLE_LABELS[role]}
        for role in sorted(ALL_ROLES)
    ]


def _validate_role(role: str) -> str:
    normalized = normalize_role(role)
    if normalized not in ALL_ROLES:
        raise http_error(400, "Invalid role selected")
    return normalized


def create_admin_user(db: Session, data: AdminUserCreate) -> User:
    username = (data.username or "").strip()
    if not username:
        raise http_error(400, "Username is required")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise http_error(400, "Username already exists")

    user = User(
        username=username,
        hashed_password=hash_password(data.password),
        role=_validate_role(data.role),
        is_active=bool(data.is_active),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def update_admin_user(
    db: Session,
    user_id: int,
    data: AdminUserUpdate,
    acting_username: str,
) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise http_error(404, "User not found")

    if user.username == acting_username and data.is_active is False:
        raise http_error(400, "You cannot deactivate your own account")

    if data.role is not None:
        user.role = _validate_role(data.role)

    if data.is_active is not None:
        user.is_active = bool(data.is_active)

    db.commit()
    db.refresh(user)
    return user


def reset_user_password(db: Session, user_id: int, new_password: str) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise http_error(404, "User not found")

    user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
