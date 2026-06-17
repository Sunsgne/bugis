"""Auth & user schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MfaMethod, UserRole, UserScope
from app.schemas.common import TimestampedSchema


class Token(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None
    mfa_methods: list[str] = Field(default_factory=list)
    captcha_required: bool = False


class LoginJsonRequest(BaseModel):
    username: str
    password: str
    turnstile_token: str | None = None
    mfa_token: str | None = None
    mfa_code: str | None = None


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str
    method: str = "totp"


class MfaSendEmailRequest(BaseModel):
    mfa_token: str


class MfaSetupTotpOut(BaseModel):
    secret: str
    provisioning_uri: str


class MfaConfirmTotpRequest(BaseModel):
    code: str


class MfaDisableRequest(BaseModel):
    password: str
    code: str


class LoginSecurityOut(BaseModel):
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""
    captcha_required_default: bool = False


class StreamTicketOut(BaseModel):
    ticket: str
    expires_in: int


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


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("role")
    @classmethod
    def platform_role_only(cls, v: UserRole | None) -> UserRole | None:
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
    mfa_enabled: bool = False
    mfa_method: MfaMethod = MfaMethod.NONE


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
