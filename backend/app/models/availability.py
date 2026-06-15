"""Circuit availability / interruption events."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CircuitAvailabilityEvent(Base, TimestampMixin):
    """Recorded downtime window for a circuit (interruption or flash)."""

    __tablename__ = "circuit_availability_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), index=True
    )
    # interruption = sustained outage; flash = brief blip below flash threshold.
    kind: Mapped[str] = mapped_column(String(24), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="tunnel_state")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
