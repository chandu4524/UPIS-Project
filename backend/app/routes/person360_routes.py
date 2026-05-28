from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_PERSON_READ
from app.services.person360_service import (
    get_person_profile,
    get_person_relationships,
    get_person_sources,
    get_search_summary,
    search_persons,
)
from app.utils.dependencies import get_db

router = APIRouter(tags=["Person 360"])


@router.get("/persons/search")
def persons_search(
    name: Optional[str] = Query(None),
    mobile: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    village: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    confidence: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_PERSON_READ)),
):
    result = search_persons(
        db,
        name=name,
        mobile=mobile,
        district=district,
        village=village,
        department=department,
        confidence=confidence,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "message": "Person search completed",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/persons/search-summary")
def persons_search_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_PERSON_READ)),
):
    summary = get_search_summary(db)
    return {
        "success": True,
        "message": "Person search summary fetched successfully",
        "logged_in_user": current_user.username,
        **summary,
    }


@router.get("/persons/{citizen_id}")
def person_profile(
    citizen_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_PERSON_READ)),
):
    profile = get_person_profile(db, citizen_id)
    return {
        "success": True,
        "message": "Person profile fetched successfully",
        "logged_in_user": current_user.username,
        **profile,
    }


@router.get("/persons/{citizen_id}/sources")
def person_sources(
    citizen_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_PERSON_READ)),
):
    result = get_person_sources(db, citizen_id, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Person sources fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }


@router.get("/persons/{citizen_id}/relationships")
def person_relationships(
    citizen_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_PERSON_READ)),
):
    result = get_person_relationships(db, citizen_id, page=page, page_size=page_size)
    return {
        "success": True,
        "message": "Person relationships fetched successfully",
        "logged_in_user": current_user.username,
        **result,
    }

