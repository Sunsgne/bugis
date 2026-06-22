"""Circuit & endpoint schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

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
    alarm_latency_ms: float | None = Field(default=None, ge=0, le=10000)
    alarm_packet_loss_pct: float | None = Field(default=None, ge=0, le=100)
    alarm_utilization_pct: float | None = Field(default=None, ge=0, le=100)
    alarm_health_score_min: float | None = Field(default=None, ge=0, le=100)
    latency_probe_enabled: bool = True
    description: str | None = None
    egress_country: str | None = None
    egress_site_id: int | None = None
    ipt_public_ip: str | None = None
    ipt_nat_enabled: int = 1
    path_mode: PathMode = PathMode.AUTO


class CircuitAdoptBinding(BaseModel):
    device_id: int
    label: str = "A"
    interface_name: str
    access_mode: AccessMode = AccessMode.DOT1Q
    vlan_id: int | None = None
    inner_vlan_id: int | None = None


class CircuitAdoptCreate(BaseModel):
    name: str
    tenant_id: int
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    bindings: list[CircuitAdoptBinding]
    vni: int | None = None
    vsi_name: str | None = None
    vlan_id: int | None = None
    bandwidth_mbps: int | None = None
    description: str | None = None
    refresh_inventory: bool = False


class CircuitAdoptVniEndpointPreview(BaseModel):
    key: str
    device_id: int
    device_name: str
    interface_name: str
    access_mode: AccessMode = AccessMode.DOT1Q
    vlan_id: int | None = None
    inner_vlan_id: int | None = None
    vni: int
    vsi_name: str | None = None
    description: str | None = None
    rd: str | None = None
    rt: str | None = None
    adoptable: bool
    reason: str | None = None


class CircuitAdoptVniPreview(BaseModel):
    vni: int
    vsi_name: str | None = None
    rd: str | None = None
    rt: str | None = None
    endpoints: list[CircuitAdoptVniEndpointPreview]
    adoptable_count: int
    total_count: int
    existing_circuit_id: int | None = None
    existing_circuit_code: str | None = None
    existing_circuit_adopted: bool | None = None
    conflict_message: str | None = None
    can_adopt: bool


class CircuitAdoptVniCreate(BaseModel):
    name: str
    tenant_id: int
    vni: int
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    device_ids: list[int] | None = None
    endpoint_keys: list[str] | None = None
    vsi_name: str | None = None
    vlan_id: int | None = None
    bandwidth_mbps: int | None = None
    description: str | None = None
    refresh_inventory: bool = True


class CircuitDeleteScheduledOut(BaseModel):
    scheduled: bool = True
    circuit_id: int
    circuit_code: str


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
    alarm_latency_ms: float | None = Field(default=None, ge=0, le=10000)
    alarm_packet_loss_pct: float | None = Field(default=None, ge=0, le=100)
    alarm_utilization_pct: float | None = Field(default=None, ge=0, le=100)
    alarm_health_score_min: float | None = Field(default=None, ge=0, le=100)
    latency_probe_enabled: bool | None = None
    description: str | None = None
    egress_country: str | None = None
    egress_site_id: int | None = None
    ipt_public_ip: str | None = None
    ipt_nat_enabled: int | None = None
    # NOTE: status is intentionally NOT editable here — lifecycle transitions
    # (draft → active → decommissioned) must go through work orders so the
    # orchestrator runs pre-checks and pushes/withdraws config. Editing it
    # directly would desync the platform from the live network.
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
    adopted: bool = False
    endpoints: list[CircuitEndpointOut] = []
    effective_alarm_latency_ms: float | None = None
    effective_alarm_packet_loss_pct: float | None = None
    effective_alarm_utilization_pct: float | None = None
    effective_alarm_health_score_min: float | None = None
    alarm_thresholds_customized: bool = False


class CircuitOut(CircuitListOut):
    path_hops: list[CircuitPathHopSchema] = []
    segment_list: list[int] = []
