"""Circuits (专线) and their endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AccessMode, CircuitStatus, ServiceType
from app.models.mixins import TimestampMixin
from sqlalchemy import Enum as SAEnum

if TYPE_CHECKING:
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
        Enum(ServiceType), default=ServiceType.L2VPN_EVPN
    )
    status: Mapped[CircuitStatus] = mapped_column(
        Enum(CircuitStatus), default=CircuitStatus.DRAFT
    )

    # EVPN identifiers
    vni: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="circuits")
    endpoints: Mapped[list["CircuitEndpoint"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(
        back_populates="circuit", cascade="all, delete-orphan"
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
    # Customer access (attachment circuit) encapsulation.
    access_mode: Mapped[AccessMode] = mapped_column(
        SAEnum(AccessMode), default=AccessMode.DOT1Q
    )
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # S-VID / access VLAN
    inner_vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # C-VID (QinQ)
    # Customer-facing IP (for L3VPN IRB gateway)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    circuit: Mapped["Circuit"] = relationship(back_populates="endpoints")
    device: Mapped["Device"] = relationship()
