"""Integration / webhook schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ServiceType


class WebhookEndpoint(BaseModel):
    label: str = "A"
    device_name: str
    interface_name: str
    vlan_id: int | None = None
    gateway_ip: str | None = None


class WebhookProvision(BaseModel):
    """StackStorm-style intent payload to create + provision a circuit."""

    tenant_code: str
    name: str
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    bandwidth_mbps: int = 100
    sla_target: str | None = None
    endpoints: list[WebhookEndpoint]
    auto_provision: bool = True
