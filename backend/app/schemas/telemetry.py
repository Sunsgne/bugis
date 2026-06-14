"""Telemetry schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import TimestampedSchema


class TelemetrySampleIn(BaseModel):
    circuit_id: int | None = None
    device_id: int | None = None
    interface_name: str | None = None
    rx_mbps: float = 0.0
    tx_mbps: float = 0.0
    utilization_pct: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_pct: float = 0.0
    errors: int = 0
    tunnel_state: str | None = None


class TelemetrySampleOut(TelemetrySampleIn, TimestampedSchema):
    id: int


class CircuitHealth(BaseModel):
    circuit_id: int
    circuit_code: str
    status: str
    sla_target: str | None = None
    avg_latency_ms: float = 0.0
    avg_jitter_ms: float = 0.0
    avg_packet_loss_pct: float = 0.0
    avg_utilization_pct: float = 0.0
    peak_utilization_pct: float = 0.0
    bandwidth_mbps: int = 0
    samples: int = 0
    health_score: float = 100.0
