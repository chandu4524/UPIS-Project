from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_SEARCH_READ
from app.services.audit_service import ACTION_INTELLIGENCE_SEARCH, log_action
from app.services.intelligence_search_service import intelligence_search
from app.services.person360_search import intelligence_search_360
from app.services.sensitive_access_service import prepare_citizen_list_response
from app.utils.dependencies import get_db

router = APIRouter(tags=["Intelligence Search"])


@router.get("/intelligence-search")
def search_intelligence(
    q: Optional[str] = Query("", description="Fuzzy search query"),
    limit: int = Query(25, ge=1, le=100),
    mode: str = Query("360", description="Search mode: 360 (default) or legacy"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_SEARCH_READ)),
):
    if (mode or "360").strip().lower() == "legacy":
        result = intelligence_search(db, query=q or "", limit=limit)
    else:
        result = intelligence_search_360(db, query=q or "", limit=limit)

    if result["query"]:
        log_action(
            db,
            username=current_user.username,
            action_type=ACTION_INTELLIGENCE_SEARCH,
            entity_type="intelligence_search",
            entity_id=result["query"][:120],
        )

    combined = list(result.get("results", [])) + list(result.get("staging_results", []))
    items, access_meta = prepare_citizen_list_response(
        db,
        combined,
        current_user,
        log_list=bool(combined),
        list_context=f"search:{result.get('query', '')[:80]}",
    )

    masked_results = items[: len(result.get("results", []))]
    staging_count = len(result.get("staging_results", []))
    masked_staging = items[len(result.get("results", [])) : len(result.get("results", [])) + staging_count]

    return {
        "success": True,
        "message": "Intelligence search completed",
        "logged_in_user": current_user.username,
        **access_meta,
        **{**result, "results": masked_results, "staging_results": masked_staging},
    }
