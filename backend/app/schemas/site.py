"""Site / DC schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import DeliveryMode
from app.schemas.common import TimestampedSchema


class SiteBase(BaseModel):
    name: str
    code: str
    region: str | None = None
    address: str | None = None
    bgp_asn: int | None = None
    underlay_prefix: str | None = None
    description: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.DIRECT
    controller_id: int | None = None


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    address: str | None = None
    bgp_asn: int | None = None
    underlay_prefix: str | None = None
    description: str | None = None
    delivery_mode: DeliveryMode | None = None
    controller_id: int | None = None


class SiteOut(SiteBase, TimestampedSchema):
    id: int
