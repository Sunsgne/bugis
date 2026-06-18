"""Circuits (专线) and their endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AccessMode, CircuitStatus, PathMode, ServiceType
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.circuit_probe_log import CircuitProbeLog
    from app.models.device import Device
    from app.models.tenant import Tenant
    from app.models.workorder import WorkOrder


class Circuit(Base, TimestampMixin):
    """A provisioned line / EVPN service instance for a tenant."""

    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    service_type: Mapped[ServiceType] = mapped_column(
        str_enum_column(ServiceType), default=ServiceType.L2VPN_EVPN
    )
    status: Mapped[CircuitStatus] = mapped_column(
        str_enum_column(CircuitStatus), default=CircuitStatus.DRAFT
    )

    # EVPN identifiers
    vni: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    vsi_name: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vrf_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_distinguisher: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # EVPN Ethernet Segment Identifier for multi-homing
    esi: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Service parameters
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100)
    mtu: Mapped[int] = mapped_column(Integer, default=9000)
    # SLA target (e.g. "99.99") and class of service
    sla_target: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cos: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Optional per-circuit alarm overrides (null → platform defaults).
    alarm_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    alarm_packet_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    alarm_utilization_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    alarm_health_score_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    # When false, skip scheduled/on-demand path probes and hide QoS metrics in UI.
    latency_probe_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Remote IPT: breakout in another country/region via overlay to border.
    egress_country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    egress_site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    ipt_public_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ipt_nat_enabled: Mapped[int] = mapped_column(Integer, default=1)

    # Underlay path: auto (OSPF/BGP best effort) or SR-MPLS explicit segment list.
    path_mode: Mapped[PathMode] = mapped_column(
        str_enum_column(PathMode), default=PathMode.AUTO
    )
    # Imported from live device inventory — never push config on provision/decommission.
    adopted: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="circuits")
    endpoints: Mapped[list["CircuitEndpoint"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan"
    )
    path_hops: Mapped[list["CircuitPathHop"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan",
        order_by="CircuitPathHop.sequence",
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan"
    )
    probe_logs: Mapped[list["CircuitProbeLog"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan",
        order_by="CircuitProbeLog.id.desc()",
    )


class CircuitEndpoint(Base, TimestampMixin):
    """An attachment point (A-end / Z-end) of a circuit on a device."""

    __tablename__ = "circuit_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE")
    )
    # Logical label such as "A" / "Z" / "spoke-1"
    label: Mapped[str] = mapped_column(String(32), default="A")
    interface_name: Mapped[str] = mapped_column(String(64))
    interface_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Customer access (attachment circuit) encapsulation.
    access_mode: Mapped[AccessMode] = mapped_column(
        str_enum_column(AccessMode), default=AccessMode.DOT1Q
    )
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # S-VID / access VLAN
    inner_vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # C-VID (QinQ)
    # Customer-facing IP (for L3VPN IRB gateway)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    circuit: Mapped["Circuit"] = relationship(back_populates="endpoints")
    device: Mapped["Device"] = relationship()


class CircuitPathHop(Base, TimestampMixin):
    """Ordered transit device on an SR-MPLS explicit path (between A/Z endpoints)."""

    __tablename__ = "circuit_path_hops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    circuit_id: Mapped[int] = mapped_column(
        ForeignKey("circuits.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    circuit: Mapped["Circuit"] = relationship(back_populates="path_hops")
    device: Mapped["Device"] = relationship()
