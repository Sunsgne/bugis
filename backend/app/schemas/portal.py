"""Tenant portal API schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import CircuitStatus, ServiceType
from app.schemas.circuit import CircuitEndpointOut
from app.schemas.common import TimestampedSchema
from app.schemas.tenant import TenantSummary


class PortalMeOut(BaseModel):
    user_id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    role: str
    tenant_id: int
    tenant_name: str
    tenant_code: str


class PortalDashboardOut(BaseModel):
    summary: TenantSummary
    active_alarms: int
    avg_health_score: float
    circuits_monitorable: int


class PortalCircuitListOut(TimestampedSchema):
    id: int
    code: str
    name: str
    service_type: ServiceType
    status: CircuitStatus
    bandwidth_mbps: int
    vni: int | None = None
    vsi_name: str | None = None
    sla_target: str | None = None
    latency_probe_enabled: bool = True
    endpoint_count: int = 0


class PortalCircuitOut(PortalCircuitListOut):
    description: str | None = None
    endpoints: list[CircuitEndpointOut] = []
    path_mode: str | None = None
