"""Auth & user schemas."""
from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.models.enums import UserRole, UserScope
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

    @field_validator("role")
    @classmethod
    def platform_role_only(cls, v: UserRole) -> UserRole:
        if v in (UserRole.TENANT_ADMIN, UserRole.TENANT_VIEWER):
            raise ValueError("use tenant user API for portal accounts")
        return v


class TenantUserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    email: str | None = None
    role: UserRole = UserRole.TENANT_VIEWER

    @field_validator("role")
    @classmethod
    def tenant_role_only(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.TENANT_ADMIN, UserRole.TENANT_VIEWER):
            raise ValueError("tenant portal role must be tenant_admin or tenant_viewer")
        return v


class UserOut(TimestampedSchema):
    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    role: UserRole
    scope: UserScope = UserScope.PLATFORM
    tenant_id: int | None = None
    is_active: bool


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
