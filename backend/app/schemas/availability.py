"""Availability / interruption schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AvailabilityEventOut(BaseModel):
    id: int
    circuit_id: int
    kind: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_sec: float | None = None
    source: str
    detail: str | None = None

    model_config = {"from_attributes": True}


class CircuitAvailabilityOut(BaseModel):
    circuit_id: int
    circuit_code: str
    hours: int
    uptime_pct: float
    interruption_count: int
    flash_count: int
    total_downtime_sec: float
    avg_latency_ms: float
    flap_count: int
    events: list[AvailabilityEventOut]
