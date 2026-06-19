"""Link schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

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
    supplier: str | None = Field(default=None, max_length=128)
    alarm_utilization_pct: float | None = Field(default=None, ge=0, le=100)


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    name: str | None = None
    type: LinkType | None = None
    device_a_id: int | None = None
    device_z_id: int | None = None
    interface_a: str | None = None
    interface_z: str | None = None
    capacity_mbps: int | None = None
    reserved_mbps: int | None = None
    description: str | None = None
    supplier: str | None = Field(default=None, max_length=128)
    alarm_utilization_pct: float | None = Field(default=None, ge=0, le=100)


class LinkOut(LinkBase, TimestampedSchema):
    id: int
    effective_alarm_utilization_pct: float | None = None
    alarm_thresholds_customized: bool = False


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
    interface_a_description: str | None = None
    interface_z_description: str | None = None
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
    description: str | None = None
