"""Alarms raised from SLA / capacity / device-state evaluation."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AlarmSeverity, AlarmStatus
from app.models.mixins import TimestampMixin, str_enum_column


class Alarm(Base, TimestampMixin):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    severity: Mapped[AlarmSeverity] = mapped_column(
        str_enum_column(AlarmSeverity), default=AlarmSeverity.WARNING, index=True
    )
    status: Mapped[AlarmStatus] = mapped_column(
        str_enum_column(AlarmStatus), default=AlarmStatus.ACTIVE, index=True
    )
    # Logical alarm type, e.g. "sla_loss", "utilization", "tunnel_down".
    kind: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    circuit_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), nullable=True, index=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # De-duplication key so we don't raise the same active alarm repeatedly.
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
