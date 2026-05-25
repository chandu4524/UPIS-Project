from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_USERS_ADMIN, normalize_role, role_label
from app.core.exceptions import http_error
from app.schemas.user_schema import UserCreate
from app.services.audit_service import ACTION_LOGIN, log_action
from app.services.user_service import create_user, authenticate_user
from app.utils.dependencies import get_db

router = APIRouter(tags=["Authentication"])


@router.post("/create-user")
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_ADMIN)),
):
    new_user = create_user(db, user)
    return {
        "success": True,
        "message": "User created successfully",
        "user_id": new_user.id,
        "role": normalize_role(new_user.role),
        "role_label": role_label(new_user.role),
        "created_by": current_user.username,
    }


@router.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    if not username or not password:
        raise http_error(400, "Username and password are required")

    result, error = authenticate_user(db, username, password)
    if error:
        raise http_error(401, error)

    log_action(
        db,
        username=username,
        action_type=ACTION_LOGIN,
        entity_type="user",
        entity_id=username,
    )

    return {
        "success": True,
        **result,
    }
