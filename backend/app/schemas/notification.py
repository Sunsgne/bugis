"""Notification channel schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AlarmSeverity, NotificationType
from app.schemas.common import TimestampedSchema


class ChannelBase(BaseModel):
    name: str
    type: NotificationType = NotificationType.WEBHOOK
    url: str
    min_severity: AlarmSeverity = AlarmSeverity.MAJOR
    active: bool = True


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    min_severity: AlarmSeverity | None = None
    active: bool | None = None


class ChannelOut(ChannelBase, TimestampedSchema):
    id: int
    last_status: str | None = None
    last_dispatch_at: datetime | None = None
