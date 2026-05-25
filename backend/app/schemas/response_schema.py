from typing import Any, List, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[Any] = None


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
