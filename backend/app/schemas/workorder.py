"""Work order, event and config job schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import (
    ConfigJobStatus,
    WorkOrderStatus,
    WorkOrderType,
)
from app.schemas.common import TimestampedSchema


class WorkOrderEventOut(TimestampedSchema):
    id: int
    work_order_id: int
    level: str
    message: str
    actor: str | None = None


class ConfigJobOut(TimestampedSchema):
    id: int
    work_order_id: int
    device_id: int
    status: ConfigJobStatus
    operation: str
    transport: str
    rendered_config: str | None = None
    rollback_config: str | None = None
    output: str | None = None


class WorkOrderCreate(BaseModel):
    circuit_id: int
    type: WorkOrderType = WorkOrderType.PROVISION
    title: str | None = None
    requested_by: str | None = None
    payload: str | None = None
    notes: str | None = None


class WorkOrderOut(TimestampedSchema):
    id: int
    code: str
    circuit_id: int
    type: WorkOrderType
    status: WorkOrderStatus
    title: str
    requested_by: str | None = None
    approved_by: str | None = None
    payload: str | None = None
    notes: str | None = None
    events: list[WorkOrderEventOut] = []
    config_jobs: list[ConfigJobOut] = []


class ApprovalRequest(BaseModel):
    approved_by: str
    approve: bool = True
    notes: str | None = None
