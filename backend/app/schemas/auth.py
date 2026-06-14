"""Auth & user schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import UserRole
from app.schemas.common import TimestampedSchema


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    email: str | None = None
    role: UserRole = UserRole.OPERATOR


class UserOut(TimestampedSchema):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    role: UserRole
    is_active: bool
