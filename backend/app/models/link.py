"""Links between devices, used for capacity / topology."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import LinkType
from app.models.mixins import TimestampMixin, str_enum_column


class Link(Base, TimestampMixin):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[LinkType] = mapped_column(str_enum_column(LinkType), default=LinkType.DCI)
    device_a_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    device_z_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    interface_a: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interface_z: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capacity_mbps: Mapped[int] = mapped_column(Integer, default=10000)
    # Bandwidth administratively reserved for circuits riding this link.
    reserved_mbps: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alarm_utilization_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
