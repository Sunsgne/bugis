"""Control-plane state maintained by the built-in Bugis SDN controller.

The controller behaves like an EVPN route-reflector / fabric brain: it tracks
VTEP peers and the EVPN RIB (Type-2/3/5 routes) it has computed and reflected
to the fabric.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EvpnRouteType, VtepStatus
from app.models.mixins import TimestampMixin


class VtepPeer(Base, TimestampMixin):
    """A VXLAN tunnel endpoint the controller has registered."""

    __tablename__ = "vtep_peers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    vtep_ip: Mapped[str] = mapped_column(String(64), index=True)
    asn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[VtepStatus] = mapped_column(Enum(VtepStatus), default=VtepStatus.UP)
    # Comma-separated list of VNIs this VTEP currently serves.
    vnis: Mapped[str] = mapped_column(String(512), default="")
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EvpnRoute(Base, TimestampMixin):
    """A single EVPN route in the controller's RIB."""

    __tablename__ = "evpn_routes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    route_type: Mapped[EvpnRouteType] = mapped_column(
        Enum(EvpnRouteType), index=True
    )
    vni: Mapped[int] = mapped_column(Integer, index=True)
    rd: Mapped[str] = mapped_column(String(64))
    rt: Mapped[str] = mapped_column(String(64))
    mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vtep_ip: Mapped[str] = mapped_column(String(64), index=True)
    next_hop: Mapped[str] = mapped_column(String(64))
    circuit_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), nullable=True, index=True
    )
    origin_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
