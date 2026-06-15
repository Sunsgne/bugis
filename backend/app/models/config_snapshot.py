"""Device configuration snapshots for the configuration-management module."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class DeviceConfigSnapshot(Base, TimestampMixin):
    """A versioned snapshot of a device's assembled running configuration."""

    __tablename__ = "device_config_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    # "push" (auto after provisioning) | "backup" (manual) | "import"
    source: Mapped[str] = mapped_column(String(16), default="backup")
    content: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
