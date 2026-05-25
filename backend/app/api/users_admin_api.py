from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_USERS_ADMIN
from app.schemas.user_schema import (
    AdminResetPassword,
    AdminUserCreate,
    AdminUserUpdate,
)
from app.services.admin_user_service import (
    create_admin_user,
    get_assignable_roles,
    get_user_by_id,
    list_users_paginated,
    reset_user_password,
    update_admin_user,
    user_to_admin_dict,
)
from app.services.audit_service import (
    ACTION_CREATE_USER,
    ACTION_DISABLE_USER,
    ACTION_RESET_PASSWORD,
    ACTION_UPDATE_USER,
    log_action,
)
from app.core.exceptions import http_error
from app.utils.dependencies import get_db

router = APIRouter(prefix="/users", tags=["Admin Users"])


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_ADMIN)),
):
    result = list_users_paginated(db, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Users fetched successfully",
        "logged_in_user": current_user.username,
        "assignable_roles": get_assignable_roles(),
        **result,
    }


@router.post("")
def create_user(
    body: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_ADMIN)),
):
    user = create_admin_user(db, body)
    log_action(
        db,
        username=current_user.username,
        action_type=ACTION_CREATE_USER,
        entity_type="user",
        entity_id=str(user.id),
    )
    return {
        "success": True,
        "message": "User created successfully",
        "logged_in_user": current_user.username,
        "user": user_to_admin_dict(user),
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_ADMIN)),
):
    if body.role is None and body.is_active is None:
        raise http_error(400, "Provide role and/or is_active to update")

    before_active = None
    if body.is_active is not None:
        existing = get_user_by_id(db, user_id)
        if existing:
            before_active = bool(getattr(existing, "is_active", True))

    user = update_admin_user(db, user_id, body, current_user.username)

    if body.is_active is not None and before_active and not user.is_active:
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_DISABLE_USER,
            entity_type="user",
            entity_id=str(user_id),
        )
    else:
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_UPDATE_USER,
            entity_type="user",
            entity_id=str(user_id),
        )

    return {
        "success": True,
        "message": "User updated successfully",
        "logged_in_user": current_user.username,
        "user": user_to_admin_dict(user),
    }


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: AdminResetPassword,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_USERS_ADMIN)),
):
    user = reset_user_password(db, user_id, body.password)
    log_action(
        db,
        username=current_user.username,
        action_type=ACTION_RESET_PASSWORD,
        entity_type="user",
        entity_id=str(user_id),
    )
    return {
        "success": True,
        "message": "Password reset successfully",
        "logged_in_user": current_user.username,
        "user": user_to_admin_dict(user),
    }
