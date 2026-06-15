"""Circuit & endpoint schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import AccessMode, CircuitStatus, PathMode, ServiceType
from app.schemas.common import TimestampedSchema


class CircuitEndpointBase(BaseModel):
    device_id: int
    label: str = "A"
    interface_name: str
    access_mode: AccessMode = AccessMode.DOT1Q
    vlan_id: int | None = None
    inner_vlan_id: int | None = None
    ip_address: str | None = None
    gateway_ip: str | None = None


class CircuitEndpointCreate(CircuitEndpointBase):
    pass


class CircuitEndpointUpdate(CircuitEndpointBase):
    pass


class CircuitEndpointsReplace(BaseModel):
    endpoints: list[CircuitEndpointCreate]


class CircuitEndpointOut(CircuitEndpointBase, TimestampedSchema):
    id: int
    circuit_id: int


class CircuitBase(BaseModel):
    name: str
    tenant_id: int
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    # EVPN identifiers - auto-allocated when omitted.
    vni: int | None = None
    vsi_name: str | None = None
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
    egress_country: str | None = None
    egress_site_id: int | None = None
    ipt_public_ip: str | None = None
    ipt_nat_enabled: int = 1
    path_mode: PathMode = PathMode.AUTO


class CircuitCreate(CircuitBase):
    code: str | None = None  # auto-generated when omitted
    endpoints: list[CircuitEndpointCreate] = []
    via_device_ids: list[int] = []


class CircuitUpdate(BaseModel):
    name: str | None = None
    service_type: ServiceType | None = None
    bandwidth_mbps: int | None = None
    mtu: int | None = None
    sla_target: str | None = None
    cos: str | None = None
    description: str | None = None
    egress_country: str | None = None
    egress_site_id: int | None = None
    ipt_public_ip: str | None = None
    ipt_nat_enabled: int | None = None
    status: CircuitStatus | None = None
    path_mode: PathMode | None = None


class CircuitPathHopSchema(BaseModel):
    device_id: int
    sequence: int
    device_name: str | None = None
    overlay_tech: str | None = None
    sr_node_sid: int | None = None


class CircuitListOut(CircuitBase, TimestampedSchema):
    """Lightweight list row — no path/segment computation."""

    id: int
    code: str
    status: CircuitStatus
    endpoints: list[CircuitEndpointOut] = []


class CircuitOut(CircuitListOut):
    path_hops: list[CircuitPathHopSchema] = []
    segment_list: list[int] = []
