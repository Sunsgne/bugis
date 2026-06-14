"""Alarm schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import AlarmSeverity, AlarmStatus
from app.schemas.common import TimestampedSchema


class AlarmOut(TimestampedSchema):
    id: int
    severity: AlarmSeverity
    status: AlarmStatus
    kind: str
    title: str
    detail: str | None = None
    circuit_id: int | None = None
    device_id: int | None = None
    acknowledged_by: str | None = None


class AlarmAck(BaseModel):
    acknowledged_by: str | None = None
