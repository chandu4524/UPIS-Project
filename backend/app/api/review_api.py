from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_REVIEW_WRITE
from app.services.entity_resolution_service import (
    approve_review,
    list_pending_reviews,
    merge_review_profiles,
    reject_review,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Entity Resolution"])


@router.get("/review")
def get_review_queue(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    items = list_pending_reviews(db)
    return {
        "success": True,
        "message": "Manual review queue fetched successfully",
        "logged_in_user": current_user.username,
        "items": items,
        "total": len(items),
    }


@router.post("/review/{review_id}/approve")
def approve_match(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    item = approve_review(db, review_id)
    return {
        "success": True,
        "message": "Match approved successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.post("/review/{review_id}/reject")
def reject_match(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    item = reject_review(db, review_id)
    return {
        "success": True,
        "message": "Match rejected successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.post("/review/{review_id}/merge")
def merge_match(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    result = merge_review_profiles(db, review_id)
    return {
        "success": True,
        "message": result.get("message", "Profiles merged successfully"),
        "logged_in_user": current_user.username,
        **result,
    }
