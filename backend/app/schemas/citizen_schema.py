from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CitizenResponse(BaseModel):
    id: int
    full_name: Optional[str] = None
    mobile: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    dob: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CitizenListResponse(BaseModel):
    items: list[CitizenResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
