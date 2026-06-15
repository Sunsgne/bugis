"""Records of live-network configuration learning runs."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.mixins import TimestampMixin


class DeviceLearnRun(Base, TimestampMixin):
    """One execution of the config auto-learn pipeline for a device."""

    __tablename__ = "device_learn_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="success")
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_config_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    inventory: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
