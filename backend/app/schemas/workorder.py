"""Work order, event and config job schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import (
    ConfigJobStatus,
    WorkOrderStatus,
    WorkOrderType,
)
from app.schemas.circuit import CircuitEndpointCreate
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
    device_name: str | None = None
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
    circuit_id: int | None = None
    circuit_code: str | None = None
    type: WorkOrderType
    status: WorkOrderStatus
    title: str
    requested_by: str | None = None
    approved_by: str | None = None
    payload: str | None = None
    notes: str | None = None
    events: list[WorkOrderEventOut] = []
    config_jobs: list[ConfigJobOut] = []


class ProvisionResultOut(WorkOrderOut):
    circuit_status: str
    circuit_code: str | None = None
    dry_run: bool = False


class ProvisionRequest(BaseModel):
    """Optional body for one-shot provision (e.g. endpoint migration)."""

    previous_endpoints: list[CircuitEndpointCreate] | None = None


class ApprovalRequest(BaseModel):
    approved_by: str | None = None
    approve: bool = True
    notes: str | None = None


class WorkOrderUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
