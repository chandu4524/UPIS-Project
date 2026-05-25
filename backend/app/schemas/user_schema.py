from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=4)
    role: str = Field(default="district_officer", max_length=64)


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    password: str = Field(..., min_length=4)
    role: str = Field(..., min_length=1, max_length=64)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    role: Optional[str] = Field(None, max_length=64)
    is_active: Optional[bool] = None


class AdminResetPassword(BaseModel):
    password: str = Field(..., min_length=4)


class UserResponse(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True
