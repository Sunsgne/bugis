"""Sites / data centers (DC) participating in DCI."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DeliveryMode
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.device import Device


class Site(Base, TimestampMixin):
    """A physical data center or PoP site."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # BGP AS number used inside the fabric / for DCI peering.
    bgp_asn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Loopback / underlay prefix summary for documentation.
    underlay_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Delivery: direct device push, or delegate to a fabric controller.
    delivery_mode: Mapped[DeliveryMode] = mapped_column(
        str_enum_column(DeliveryMode), default=DeliveryMode.DIRECT
    )
    controller_id: Mapped[int | None] = mapped_column(
        ForeignKey("controllers.id", ondelete="SET NULL"), nullable=True
    )

    # Devices keep their data when a site is removed; the FK is ON DELETE SET
    # NULL. Deleting a site must NOT cascade-delete its devices (and, in turn,
    # their circuits/links/config history), so no delete-orphan cascade here.
    devices: Mapped[list["Device"]] = relationship(
        back_populates="site", passive_deletes=True
    )
