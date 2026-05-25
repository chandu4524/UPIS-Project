from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_permission
from app.auth.rbac import PERM_ASSISTANT_USE
from app.services.assistant_service import process_assistant_query
from app.utils.dependencies import get_db

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


class AssistantQueryBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


@router.post("/query")
def assistant_query(
    body: AssistantQueryBody,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(PERM_ASSISTANT_USE)),
):
    result = process_assistant_query(db, body.query, username=current_user.username)
    return {
        "success": True,
        "message": "Assistant response generated",
        "logged_in_user": current_user.username,
        "answer": result.get("answer", ""),
        "intent": result.get("intent", "help"),
        "suggested_actions": result.get("suggested_actions", []),
        "related_links": result.get("related_links", []),
        "suggested_prompts": result.get("suggested_prompts", []),
    }
