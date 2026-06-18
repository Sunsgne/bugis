"""Precomputed circuit health for fast portal / list reads at scale."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CircuitHealthSnapshot(Base):
    """Latest health metrics per circuit; refreshed by the scheduler each tick."""

    __tablename__ = "circuit_health_snapshots"

    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"),
        primary_key=True,
    )
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_jitter_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    avg_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    peak_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    tunnel_down: Mapped[bool] = mapped_column(Boolean, default=False)
    qos_samples: Mapped[int] = mapped_column(Integer, default=0)
    samples: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
