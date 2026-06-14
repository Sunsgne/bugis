"""Tenant schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import TenantStatus, TenantType
from app.schemas.common import TimestampedSchema


class TenantBase(BaseModel):
    name: str
    code: str
    type: TenantType = TenantType.ENTERPRISE
    status: TenantStatus = TenantStatus.ACTIVE
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    cloud_account: str | None = None
    description: str | None = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: str | None = None
    type: TenantType | None = None
    status: TenantStatus | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    cloud_account: str | None = None
    description: str | None = None


class TenantOut(TenantBase, TimestampedSchema):
    id: int
