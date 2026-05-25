"""Authentication dependencies with RBAC."""

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.auth.rbac import has_any_permission, normalize_role, role_label
from app.core.config import JWT_ALGORITHM, SECRET_KEY
from app.core.exceptions import http_error
from app.models.user import User
from app.utils.dependencies import get_db

security = HTTPBearer()


@dataclass
class CurrentUser:
    username: str
    role: str
    role_label: str


def _user_from_db(db: Session, username: str) -> Optional[CurrentUser]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    role = normalize_role(user.role)
    return CurrentUser(username=user.username, role=role, role_label=role_label(role))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise http_error(401, "Invalid token")

        token_role = payload.get("role")
        if token_role:
            role = normalize_role(token_role)
            return CurrentUser(
                username=username,
                role=role,
                role_label=role_label(role),
            )

        db_user = _user_from_db(db, username)
        if db_user:
            return db_user
        raise http_error(401, "Invalid token")
    except JWTError as exc:
        raise http_error(401, "Invalid or expired token") from exc


def verify_token(
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    """Backward-compatible: returns username only."""
    return current_user.username


def require_permission(
    *permissions: str,
) -> Callable[..., CurrentUser]:
    """FastAPI dependency factory — user must hold at least one permission."""

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not permissions:
            return current_user
        if not has_any_permission(current_user.role, set(permissions)):
            raise http_error(
                403,
                "You do not have permission to access this resource",
                {"required_permissions": list(permissions), "role": current_user.role},
            )
        return current_user

    return _dependency


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Require one of the given canonical roles."""

    allowed = {normalize_role(r) for r in roles}

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed and current_user.role != "admin":
            raise http_error(403, "This action is restricted to authorized roles only")
        return current_user

    return _dependency
