"""Backward-compatible auth exports — prefer app.auth.deps for RBAC."""

from app.auth.deps import CurrentUser, get_current_user, security, verify_token

ALGORITHM = "HS256"

__all__ = [
    "ALGORITHM",
    "CurrentUser",
    "get_current_user",
    "security",
    "verify_token",
]