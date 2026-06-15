"""Rendered configuration jobs pushed (or dry-run) to devices."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ConfigJobStatus
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.workorder import WorkOrder


class ConfigJob(Base, TimestampMixin):
    """One unit of configuration targeted at a single device."""

    __tablename__ = "config_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    status: Mapped[ConfigJobStatus] = mapped_column(
        str_enum_column(ConfigJobStatus), default=ConfigJobStatus.PENDING
    )
    # Operation intent: "apply" or "remove"
    operation: Mapped[str] = mapped_column(String(16), default="apply")
    # Rendered vendor configuration (CLI / netconf payload).
    rendered_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rollback configuration, for safe decommission / failure recovery.
    rollback_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Output / log captured while pushing.
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport: Mapped[str] = mapped_column(String(16), default="netconf")

    work_order: Mapped["WorkOrder"] = relationship(back_populates="config_jobs")
    device: Mapped["Device"] = relationship()
