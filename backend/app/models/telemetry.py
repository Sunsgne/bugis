"""Telemetry samples for SLA / bandwidth visualization."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class TelemetrySample(Base, TimestampMixin):
    """A point-in-time measurement for a circuit or device interface."""

    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), nullable=True, index=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True
    )
    interface_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    rx_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    tx_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    jitter_ms: Mapped[float] = mapped_column(Float, default=0.0)
    packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    # Derived tunnel/BGP state, e.g. "up" / "down"
    tunnel_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # snmp | snmp-link | probe | manual | unavailable | legacy
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, default="unknown")
