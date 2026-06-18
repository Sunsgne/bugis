"""Network devices and their interfaces."""
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    DeviceRole,
    DeviceStatus,
    ManagementTransport,
    OverlayTech,
    Vendor,
)
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.site import Site


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    hostname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[Vendor] = mapped_column(str_enum_column(Vendor), index=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[DeviceRole] = mapped_column(str_enum_column(DeviceRole), default=DeviceRole.LEAF)
    overlay_tech: Mapped[OverlayTech] = mapped_column(
        str_enum_column(OverlayTech), default=OverlayTech.VXLAN_EVPN
    )
    status: Mapped[DeviceStatus] = mapped_column(
        str_enum_column(DeviceStatus), default=DeviceStatus.UNKNOWN
    )

    # Management / southbound connectivity
    mgmt_ip: Mapped[str] = mapped_column(String(64))
    mgmt_ip_backup: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mgmt_ip_primary_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mgmt_ip_backup_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mgmt_ip_active: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mgmt_ip_active_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_reachability_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reachability_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_reachability_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    management_transport: Mapped[ManagementTransport] = mapped_column(
        str_enum_column(ManagementTransport), default=ManagementTransport.AUTO
    )
    netconf_port: Mapped[int] = mapped_column(Integer, default=830)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NOTE: store credentials encrypted / in a vault in production.
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enable_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    netmiko_device_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # SNMP (optional per device; empty community falls back to platform default)
    snmp_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    snmp_port: Mapped[int] = mapped_column(Integer, default=161)
    snmp_community: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snmp_version: Mapped[str] = mapped_column(String(8), default="2c")
    snmp_v3_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snmp_v3_auth_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snmp_v3_priv_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snmp_v3_security_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    snmp_v3_auth_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    snmp_v3_priv_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)

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

    @property
    def active_mgmt_ip(self) -> str:
        """Southbound target: last successful IP or primary."""
        return self.mgmt_ip_active or self.mgmt_ip

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
