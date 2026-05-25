from datetime import datetime

from app.auth.auth_handler import create_access_token, hash_password, verify_password
from app.auth.rbac import normalize_role, role_label
from app.models.user import User
from app.schemas.user_schema import UserCreate


def create_user(db, user_data: UserCreate):
    existing = db.query(User).filter(User.username == user_data.username).first()

    if existing:
        from app.core.exceptions import http_error
        raise http_error(400, "Username already exists")

    new_user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        role=normalize_role(user_data.role),
        is_active=True,
        created_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return None, "Invalid username or password"

    if not bool(getattr(user, "is_active", True)):
        return None, "Account is deactivated. Contact an administrator."

    if not verify_password(password, user.hashed_password):
        return None, "Invalid username or password"

    role = normalize_role(user.role)
    token = create_access_token({"sub": user.username, "role": role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "role_label": role_label(role),
        "username": user.username,
    }, None