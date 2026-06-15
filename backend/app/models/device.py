"""Network devices and their interfaces."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    DeviceRole,
    DeviceStatus,
    OverlayTech,
    Vendor,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.site import Site


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    hostname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[Vendor] = mapped_column(Enum(Vendor), index=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[DeviceRole] = mapped_column(Enum(DeviceRole), default=DeviceRole.LEAF)
    overlay_tech: Mapped[OverlayTech] = mapped_column(
        Enum(OverlayTech), default=OverlayTech.VXLAN_EVPN
    )
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus), default=DeviceStatus.UNKNOWN
    )

    # Management / southbound connectivity
    mgmt_ip: Mapped[str] = mapped_column(String(64))
    netconf_port: Mapped[int] = mapped_column(Integer, default=830)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NOTE: store credentials encrypted / in a vault in production.
    # Also used as SNMP read community override when prefer_device_community is on.
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @property
    def password_set(self) -> bool:
        return bool(self.password)

    # Routing identity
    loopback_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bgp_asn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # SR / SRGB base for SR-MPLS capable devices
    sr_node_sid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_route_reflector: Mapped[bool] = mapped_column(Boolean, default=False)

    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    site: Mapped["Site | None"] = relationship(back_populates="devices")

    interfaces: Mapped[list["DeviceInterface"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DeviceInterface(Base, TimestampMixin):
    __tablename__ = "device_interfaces"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(64))  # e.g. GE1/0/1, et-0/0/0
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    speed_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_up: Mapped[bool] = mapped_column(Boolean, default=True)
    # Whether the port is currently allocated to a circuit endpoint.
    allocated: Mapped[bool] = mapped_column(Boolean, default=False)
    # S-VID / encapsulation inventory from platform + device scan.
    used_s_vids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # SNMP-discovered attributes (IF-MIB).
    ifindex: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oper_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    discovered_via: Mapped[str | None] = mapped_column(String(16), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="interfaces")
