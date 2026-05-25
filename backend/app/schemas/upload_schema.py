from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: int
    filename: str
    uploaded_rows: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class UploadListItem(BaseModel):
    id: int
    filename: str
    uploaded_rows: int
    uploaded_at: datetime
    status: str
    uploaded_by: Optional[str] = None

    class Config:
        from_attributes = True


class UploadResultSchema(BaseModel):
    success: bool
    message: str
    file_id: int
    filename: str
    rows_imported: int
    rows_skipped: int = 0
    preview_data: Optional[List[Dict[str, Any]]] = None
