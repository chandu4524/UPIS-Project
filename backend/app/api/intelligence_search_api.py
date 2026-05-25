from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_SEARCH_READ
from app.services.audit_service import ACTION_INTELLIGENCE_SEARCH, log_action
from app.services.intelligence_search_service import intelligence_search
from app.services.sensitive_access_service import prepare_citizen_list_response
from app.utils.dependencies import get_db

router = APIRouter(tags=["Intelligence Search"])


@router.get("/intelligence-search")
def search_intelligence(
    q: Optional[str] = Query("", description="Fuzzy search query"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_SEARCH_READ)),
):
    result = intelligence_search(db, query=q or "", limit=limit)
    if result["query"]:
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_INTELLIGENCE_SEARCH,
            entity_type="intelligence_search",
            entity_id=result["query"][:120],
        )
    items, access_meta = prepare_citizen_list_response(
        db,
        result.get("results", []),
        current_user,
        log_list=bool(result.get("results")),
        list_context=f"search:{result.get('query', '')[:80]}",
    )
    return {
        "success": True,
        "message": "Intelligence search completed",
        "logged_in_user": current_user.username,
        **access_meta,
        **{**result, "results": items},
    }
