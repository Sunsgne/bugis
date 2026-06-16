"""Persisted circuit probe run history."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CircuitProbeLog(Base, TimestampMixin):
    __tablename__ = "circuit_probe_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(16))
    probe_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    rtt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    jitter_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    packet_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    path_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    circuit: Mapped["Circuit"] = relationship(back_populates="probe_logs")  # noqa: F821
