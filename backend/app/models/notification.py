"""Outbound notification channels for alarms."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AlarmSeverity, NotificationType
from app.models.mixins import TimestampMixin, str_enum_column


class NotificationChannel(Base, TimestampMixin):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[NotificationType] = mapped_column(str_enum_column(NotificationType))
    url: Mapped[str] = mapped_column(String(512))
    min_severity: Mapped[AlarmSeverity] = mapped_column(
        str_enum_column(AlarmSeverity), default=AlarmSeverity.MAJOR
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_dispatch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
