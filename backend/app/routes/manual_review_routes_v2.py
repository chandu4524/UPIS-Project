from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_REVIEW_WRITE
from app.services.manual_review_service_v2 import (
    approve_candidate,
    get_candidate,
    list_pending,
    merge_candidate,
    reject_candidate,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Manual Review v2"])


@router.get("/review-candidates/pending")
def pending_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    result = list_pending(db, page=page, page_size=page_size, category=category)
    return {
        "success": True,
        "message": "Review candidates fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/review-candidates/{candidate_id}")
def candidate_detail(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    item = get_candidate(db, candidate_id)
    return {
        "success": True,
        "message": "Review candidate fetched successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.post("/review-candidates/{candidate_id}/approve")
def approve(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    item = approve_candidate(db, candidate_id, username=current_user.username)
    return {
        "success": True,
        "message": "Candidate approved successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.post("/review-candidates/{candidate_id}/reject")
def reject(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    item = reject_candidate(db, candidate_id, username=current_user.username)
    return {
        "success": True,
        "message": "Candidate rejected successfully",
        "logged_in_user": current_user.username,
        "item": item,
    }


@router.post("/review-candidates/{candidate_id}/merge")
def merge(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_REVIEW_WRITE)),
):
    result = merge_candidate(db, candidate_id, username=current_user.username)
    return {
        "success": True,
        "logged_in_user": current_user.username,
        **result,
    }

