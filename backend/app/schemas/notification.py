"""Notification channel schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.url_validation import validate_outbound_http_url
from app.models.enums import AlarmSeverity, NotificationType
from app.schemas.common import TimestampedSchema


class ChannelBase(BaseModel):
    name: str
    type: NotificationType = NotificationType.WEBHOOK
    url: str
    min_severity: AlarmSeverity = AlarmSeverity.MAJOR
    active: bool = True

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str, info) -> str:
        if info.data.get("type") == NotificationType.EMAIL:
            return v.strip()
        return validate_outbound_http_url(v, field="url")


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    min_severity: AlarmSeverity | None = None
    active: bool | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if stripped.startswith(("http://", "https://")):
            return validate_outbound_http_url(stripped, field="url")
        return stripped


class ChannelOut(ChannelBase, TimestampedSchema):
    id: int
    last_status: str | None = None
    last_dispatch_at: datetime | None = None
