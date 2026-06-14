"""Site / DC schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import TimestampedSchema


class SiteBase(BaseModel):
    name: str
    code: str
    region: str | None = None
    address: str | None = None
    bgp_asn: int | None = None
    underlay_prefix: str | None = None
    description: str | None = None


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    address: str | None = None
    bgp_asn: int | None = None
    underlay_prefix: str | None = None
    description: str | None = None


class SiteOut(SiteBase, TimestampedSchema):
    id: int
