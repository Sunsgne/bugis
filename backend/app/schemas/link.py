"""Link schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import LinkType
from app.schemas.common import TimestampedSchema


class LinkBase(BaseModel):
    name: str
    type: LinkType = LinkType.DCI
    device_a_id: int
    device_z_id: int
    interface_a: str | None = None
    interface_z: str | None = None
    capacity_mbps: int = 10000
    reserved_mbps: int = 0
    description: str | None = None


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    name: str | None = None
    type: LinkType | None = None
    interface_a: str | None = None
    interface_z: str | None = None
    capacity_mbps: int | None = None
    reserved_mbps: int | None = None
    description: str | None = None


class LinkOut(LinkBase, TimestampedSchema):
    id: int


class LinkPlanOut(BaseModel):
    device_a_id: int
    device_z_id: int
    device_a: str
    device_z: str
    site_a: str | None = None
    site_z: str | None = None
    type: LinkType
    name: str
    interface_a: str
    interface_z: str
    interface_a_score: float | None = None
    interface_z_score: float | None = None
    interface_a_reason: str | None = None
    interface_z_reason: str | None = None
    capacity_mbps: int
    score: float
    reason: str
    recommended: bool = False


class LinkBulkCreate(BaseModel):
    links: list[LinkCreate]


class InterfaceCandidateOut(BaseModel):
    name: str
    speed_mbps: int
    oper_status: str | None = None
    score: float
    reason: str
