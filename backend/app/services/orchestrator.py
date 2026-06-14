"""Orchestration engine.

Implements the work-order driven provisioning pipeline that shields the
northbound layer from vendor differences:

    draft -> submitted -> approved -> running -> completed / failed

For each circuit endpoint (and DCI gateway when relevant) the engine renders
vendor configuration via the appropriate southbound driver and applies it
(dry-run by default).
"""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.drivers import get_driver
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.config_job import ConfigJob
from app.models.device import Device
from app.models.enums import (
    CircuitStatus,
    ConfigJobStatus,
    DeviceRole,
    ServiceType,
    WorkOrderStatus,
    WorkOrderType,
)
from app.models.site import Site
from app.models.workorder import WorkOrder, WorkOrderEvent
from app.services import validation


def _log(db: Session, wo: WorkOrder, message: str, level: str = "info",
         actor: str | None = None) -> None:
    db.add(
        WorkOrderEvent(
            work_order_id=wo.id, level=level, message=message, actor=actor
        )
    )


def next_work_order_code(db: Session) -> str:
    while True:
        code = "WO-" + secrets.token_hex(3).upper()
        if not db.execute(
            select(WorkOrder.id).where(WorkOrder.code == code)
        ).first():
            return code


# --- lifecycle transitions ------------------------------------------------
def create_work_order(
    db: Session,
    circuit: Circuit,
    wo_type: WorkOrderType,
    title: str | None = None,
    requested_by: str | None = None,
    payload: str | None = None,
    notes: str | None = None,
) -> WorkOrder:
    wo = WorkOrder(
        code=next_work_order_code(db),
        circuit_id=circuit.id,
        type=wo_type,
        status=WorkOrderStatus.DRAFT,
        title=title or f"{wo_type.value} circuit {circuit.code}",
        requested_by=requested_by,
        payload=payload,
        notes=notes,
    )
    db.add(wo)
    db.flush()
    _log(db, wo, f"Work order created ({wo_type.value})", actor=requested_by)
    return wo


def submit(db: Session, wo: WorkOrder, actor: str | None = None) -> WorkOrder:
    if wo.status not in (WorkOrderStatus.DRAFT, WorkOrderStatus.REJECTED):
        raise ValueError(f"cannot submit work order in status {wo.status.value}")
    wo.status = WorkOrderStatus.SUBMITTED
    _log(db, wo, "Work order submitted for approval", actor=actor)
    return wo


def approve(
    db: Session, wo: WorkOrder, approver: str, approve_it: bool = True,
    notes: str | None = None,
) -> WorkOrder:
    if wo.status != WorkOrderStatus.SUBMITTED:
        raise ValueError("only submitted work orders can be approved/rejected")
    if approve_it:
        wo.status = WorkOrderStatus.APPROVED
        wo.approved_by = approver
        _log(db, wo, f"Approved by {approver}", actor=approver)
    else:
        wo.status = WorkOrderStatus.REJECTED
        _log(db, wo, f"Rejected by {approver}: {notes or ''}",
             level="warning", actor=approver)
    return wo


# --- provisioning execution ----------------------------------------------
def _operation_for(wo_type: WorkOrderType) -> str:
    if wo_type == WorkOrderType.DECOMMISSION:
        return "remove"
    return "apply"


def _build_context(circuit: Circuit, endpoint: CircuitEndpoint,
                   device: Device, site: Site | None) -> dict:
    return {
        "circuit": circuit,
        "endpoint": endpoint,
        "device": device,
        "site": site,
    }


def _dci_gateways(db: Session, circuit: Circuit) -> list[Device]:
    """Return DCI/border gateways at sites that host this circuit's endpoints."""
    site_ids = set()
    for ep in circuit.endpoints:
        if ep.device and ep.device.site_id:
            site_ids.add(ep.device.site_id)
    if not site_ids:
        return []
    rows = db.execute(
        select(Device).where(
            Device.site_id.in_(site_ids),
            Device.role.in_([DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF]),
        )
    ).scalars().all()
    return list(rows)


def execute(db: Session, wo: WorkOrder, actor: str | None = None) -> WorkOrder:
    """Render and apply configuration for a work order."""
    if wo.status not in (WorkOrderStatus.APPROVED, WorkOrderStatus.SCHEDULED):
        raise ValueError("work order must be approved before execution")

    circuit = wo.circuit

    # Pre-flight compliance validation (skip for decommission).
    if wo.type != WorkOrderType.DECOMMISSION:
        issues = validation.validate_circuit(db, circuit)
        errors = [i for i in issues if i.level == "error"]
        for i in issues:
            _log(db, wo, f"预检[{i.level}] {i.code}: {i.message}",
                 level="warning" if i.level != "error" else "error", actor=actor)
        if errors:
            wo.status = WorkOrderStatus.FAILED
            circuit.status = CircuitStatus.FAILED
            _log(db, wo, f"预检未通过，存在 {len(errors)} 个错误，已阻断下发",
                 level="error", actor=actor)
            return wo

    wo.status = WorkOrderStatus.RUNNING
    circuit.status = CircuitStatus.PROVISIONING
    operation = _operation_for(wo.type)
    service_type: ServiceType = circuit.service_type
    _log(db, wo, f"Execution started: {operation} {service_type.value}", actor=actor)

    targets: list[tuple[CircuitEndpoint | None, Device]] = []
    for ep in circuit.endpoints:
        if ep.device:
            targets.append((ep, ep.device))

    # For DCI services, also program the DCI gateways.
    gateway_devices: list[Device] = []
    if service_type == ServiceType.DCI or wo.type == WorkOrderType.PROVISION:
        gateway_devices = _dci_gateways(db, circuit)

    failed = False
    for endpoint, device in targets:
        ok = _render_and_push(db, wo, circuit, endpoint, device, service_type,
                              operation, actor)
        failed = failed or not ok

    for gw in gateway_devices:
        # gateways use the DCI template regardless of access service type
        ok = _render_and_push(db, wo, circuit, None, gw, ServiceType.DCI,
                              operation, actor, is_gateway=True)
        failed = failed or not ok

    if failed:
        wo.status = WorkOrderStatus.FAILED
        circuit.status = CircuitStatus.FAILED
        _log(db, wo, "Execution finished with errors", level="error", actor=actor)
    else:
        wo.status = WorkOrderStatus.COMPLETED
        if wo.type == WorkOrderType.DECOMMISSION:
            circuit.status = CircuitStatus.DECOMMISSIONED
        else:
            circuit.status = CircuitStatus.ACTIVE
        _log(db, wo, "Execution completed successfully", actor=actor)
    return wo


def _render_and_push(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    endpoint: CircuitEndpoint | None,
    device: Device,
    service_type: ServiceType,
    operation: str,
    actor: str | None,
    is_gateway: bool = False,
) -> bool:
    driver = get_driver(device.vendor)
    site = device.site
    # Use a synthetic endpoint for gateway-only jobs.
    ep = endpoint or CircuitEndpoint(
        circuit_id=circuit.id,
        device_id=device.id,
        label="GW",
        interface_name="-",
        vlan_id=circuit.vlan_id,
        gateway_ip=None,
    )
    context = _build_context(circuit, ep, device, site)

    job = ConfigJob(
        work_order_id=wo.id,
        device_id=device.id,
        operation=operation,
        transport=driver.transport,
        status=ConfigJobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    try:
        rendered = driver.render(service_type.value, operation, context)
        job.rendered_config = rendered
        job.status = ConfigJobStatus.RENDERED
        # Render the inverse op as rollback config (best-effort).
        inverse = "remove" if operation == "apply" else "apply"
        try:
            job.rollback_config = driver.render(service_type.value, inverse, context)
        except Exception:
            job.rollback_config = None

        result = driver.push(device, rendered, dry_run=settings.dry_run)
        job.output = result.output
        job.status = (
            ConfigJobStatus.DRY_RUN if result.dry_run and result.success
            else ConfigJobStatus.SUCCEEDED if result.success
            else ConfigJobStatus.FAILED
        )
        tag = "[GW] " if is_gateway else ""
        _log(
            db, wo,
            f"{tag}{device.vendor.value} {device.name}: {operation} "
            f"{service_type.value} -> {job.status.value}",
            level="info" if result.success else "error",
            actor=actor,
        )
        return result.success
    except Exception as exc:  # noqa: BLE001
        job.status = ConfigJobStatus.FAILED
        job.output = f"render/push error: {exc}"
        _log(db, wo, f"{device.name}: error {exc}", level="error", actor=actor)
        return False
