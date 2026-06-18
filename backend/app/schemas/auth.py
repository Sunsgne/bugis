"""Auth & user schemas."""
from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MfaMethod, UserRole, UserScope
from app.schemas.common import TimestampedSchema

SUPPORTED_LOCALES = frozenset({"zh", "en"})
DEFAULT_LOCALE = "zh"
DEFAULT_TIMEZONE = "Asia/Shanghai"


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
    password_reset_enabled: bool = False


class StreamTicketOut(BaseModel):
    ticket: str
    expires_in: int


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=128)
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
    password: str = Field(min_length=8, max_length=128)
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
    locale: str = DEFAULT_LOCALE
    timezone: str = DEFAULT_TIMEZONE


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    """Self-service profile update available to any authenticated account."""

    full_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    locale: str | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str | None) -> str | None:
        if v is None:
            return None
        code = v.strip().lower()
        if code not in SUPPORTED_LOCALES:
            raise ValueError("locale must be zh or en")
        return code

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        tz = v.strip()
        try:
            ZoneInfo(tz)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("invalid IANA timezone") from exc
        return tz


class ForgotPasswordRequest(BaseModel):
    """Initiate a password reset; accepts a username or e-mail address."""

    identifier: str = Field(min_length=1, max_length=255)
    turnstile_token: str | None = None


class ForgotPasswordOut(BaseModel):
    sent: bool = True
    detail: str = "若该账号存在且已绑定邮箱，验证码已发送至邮箱。"


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)
