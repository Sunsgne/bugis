"""Circuit & endpoint schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import CircuitStatus, ServiceType
from app.schemas.common import TimestampedSchema


class CircuitEndpointBase(BaseModel):
    device_id: int
    label: str = "A"
    interface_name: str
    vlan_id: int | None = None
    ip_address: str | None = None
    gateway_ip: str | None = None


class CircuitEndpointCreate(CircuitEndpointBase):
    pass


class CircuitEndpointOut(CircuitEndpointBase, TimestampedSchema):
    id: int
    circuit_id: int


class CircuitBase(BaseModel):
    name: str
    tenant_id: int
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    # EVPN identifiers - auto-allocated when omitted.
    vni: int | None = None
    vlan_id: int | None = None
    vrf_name: str | None = None
    route_distinguisher: str | None = None
    route_target: str | None = None
    esi: str | None = None
    bandwidth_mbps: int = 100
    mtu: int = 9000
    sla_target: str | None = None
    cos: str | None = None
    description: str | None = None


class CircuitCreate(CircuitBase):
    code: str | None = None  # auto-generated when omitted
    # Optional service offering to prefill service_type/bandwidth/sla/mtu/cos.
    offering_id: int | None = None
    endpoints: list[CircuitEndpointCreate] = []


class CircuitUpdate(BaseModel):
    name: str | None = None
    service_type: ServiceType | None = None
    bandwidth_mbps: int | None = None
    mtu: int | None = None
    sla_target: str | None = None
    cos: str | None = None
    description: str | None = None
    status: CircuitStatus | None = None


class CircuitOut(CircuitBase, TimestampedSchema):
    id: int
    code: str
    status: CircuitStatus
    endpoints: list[CircuitEndpointOut] = []
