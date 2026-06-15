"""Control-plane state maintained by the built-in Bugis SDN controller.

The controller behaves like an EVPN route-reflector / fabric brain: it tracks
VTEP peers and the EVPN RIB (Type-2/3/5 routes) it has computed and reflected
to the fabric.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import (
    BgpSessionState,
    ControllerNodeRole,
    DataPlaneState,
    EvpnEncap,
    EvpnRouteType,
    VtepStatus,
)
from app.models.mixins import TimestampMixin, str_enum_column


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
    status: Mapped[VtepStatus] = mapped_column(str_enum_column(VtepStatus), default=VtepStatus.UP)
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
        str_enum_column(EvpnRouteType), index=True
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
    encap: Mapped[EvpnEncap] = mapped_column(
        str_enum_column(EvpnEncap), default=EvpnEncap.VXLAN, index=True
    )
    mpls_label: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sr_sid: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BgpEvpnSession(Base, TimestampMixin):
    """BGP L2VPN EVPN session between Bugis controller and a fabric device."""

    __tablename__ = "bgp_evpn_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), unique=True, index=True
    )
    device_name: Mapped[str] = mapped_column(String(128))
    peer_ip: Mapped[str] = mapped_column(String(64), index=True)
    local_asn: Mapped[int] = mapped_column(Integer, default=65000)
    remote_asn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[BgpSessionState] = mapped_column(
        str_enum_column(BgpSessionState), default=BgpSessionState.IDLE, index=True
    )
    routes_received: Mapped[int] = mapped_column(Integer, default=0)
    routes_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_keepalive: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControllerClusterNode(Base, TimestampMixin):
    """Controller cluster member for HA / rib replication."""

    __tablename__ = "controller_cluster_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    node_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(128))
    role: Mapped[ControllerNodeRole] = mapped_column(
        str_enum_column(ControllerNodeRole), default=ControllerNodeRole.CANDIDATE, index=True
    )
    api_url: Mapped[str] = mapped_column(String(255), default="internal://bugis")
    rib_version: Mapped[int] = mapped_column(Integer, default=0)
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_local: Mapped[int] = mapped_column(Integer, default=0)


class DataPlaneBinding(Base, TimestampMixin):
    """Controller-tracked data-plane programming for a circuit endpoint."""

    __tablename__ = "data_plane_bindings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[str] = mapped_column(String(16), default="apply")
    transport: Mapped[str] = mapped_column(String(32), default="netconf")
    state: Mapped[DataPlaneState] = mapped_column(
        str_enum_column(DataPlaneState), default=DataPlaneState.PENDING, index=True
    )
    config_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
