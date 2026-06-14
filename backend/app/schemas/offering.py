"""Service offering schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ServiceType
from app.schemas.common import TimestampedSchema


class OfferingBase(BaseModel):
    name: str
    code: str
    service_type: ServiceType = ServiceType.L2VPN_EVPN
    bandwidth_mbps: int = 100
    sla_target: str | None = None
    cos: str | None = None
    mtu: int = 9000
    tier: str | None = None
    active: bool = True
    description: str | None = None


class OfferingCreate(OfferingBase):
    pass


class OfferingUpdate(BaseModel):
    name: str | None = None
    service_type: ServiceType | None = None
    bandwidth_mbps: int | None = None
    sla_target: str | None = None
    cos: str | None = None
    mtu: int | None = None
    tier: str | None = None
    active: bool | None = None
    description: str | None = None


class OfferingOut(OfferingBase, TimestampedSchema):
    id: int
