"""Platform settings & branding schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class BrandingOut(BaseModel):
    product_name: str
    header_title: str
    tagline: str
    login_title: str
    login_subtitle: str
    hero_title: str
    hero_subtitle: str
    logo_url: str | None = None
    logo_mark_url: str | None = None
    accent_color: str = "#52c41a"
    login_background: str | None = None


class PlatformSettingsOut(BrandingOut, TimestampedSchema):
    id: int


class BrandingUpdate(BaseModel):
    product_name: str | None = Field(default=None, max_length=128)
    header_title: str | None = Field(default=None, max_length=255)
    tagline: str | None = Field(default=None, max_length=255)
    login_title: str | None = Field(default=None, max_length=128)
    login_subtitle: str | None = Field(default=None, max_length=255)
    hero_title: str | None = Field(default=None, max_length=255)
    hero_subtitle: str | None = Field(default=None, max_length=512)
    logo_url: str | None = None
    logo_mark_url: str | None = None
    accent_color: str | None = Field(default=None, max_length=16)
    login_background: str | None = None
