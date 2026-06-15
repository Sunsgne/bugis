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
from app.controller import controller as bugis_controller
from app.controller import dataplane as ctrl_dataplane
from app.models.controller import Controller
from app.models.enums import (
    AccessMode,
    CircuitStatus,
    ConfigJobStatus,
    ControllerType,
    DeliveryMode,
    DeviceRole,
    OverlayTech,
    PathMode,
    ServiceType,
    WorkOrderStatus,
    WorkOrderType,
)
from app.models.site import Site
from app.models.workorder import WorkOrder, WorkOrderEvent
from app.services import controller_client, device_management, validation


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


def _build_context(
    circuit: Circuit,
    endpoint: CircuitEndpoint,
    device: Device,
    site: Site | None,
    *,
    is_egress: bool = False,
    is_gateway: bool = False,
    db: Session | None = None,
) -> dict:
    ctx = {
        "circuit": circuit,
        "endpoint": endpoint,
        "device": device,
        "site": site,
        "is_egress": is_egress,
        "is_gateway": is_gateway,
        "path_mode": circuit.path_mode.value,
        "path_segments": [],
        "path_devices": [],
        "is_sr_headend": False,
    }
    if db is not None:
        from app.services import path_service

        path_devs = path_service.full_path_for_circuit(db, circuit)
        ctx["path_segments"] = path_service.segment_list(path_devs)
        ctx["path_devices"] = [d.name for d in path_devs]
        if circuit.endpoints:
            first = sorted(circuit.endpoints, key=lambda e: (e.label != "A", e.label))[0]
            ctx["is_sr_headend"] = endpoint.id == first.id
    return ctx


def _render_sr_policy(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    endpoint: CircuitEndpoint,
    device: Device,
    operation: str,
    actor: str | None,
    base_job: ConfigJob,
) -> bool:
    """Append SR Policy / explicit segment-list config on the A-end PE."""
    if circuit.path_mode != PathMode.EXPLICIT_SR:
        return True
    if device.overlay_tech != OverlayTech.SRMPLS_EVPN or not endpoint:
        return True
    if not circuit.endpoints:
        return True
    first = sorted(circuit.endpoints, key=lambda e: (e.label != "A", e.label))[0]
    if endpoint.id != first.id:
        return True

    driver = get_driver(device.vendor)
    context = _build_context(
        circuit, endpoint, device, device.site, db=db,
    )
    if not context["path_segments"]:
        return True
    try:
        sr_cfg = driver.render("sr_policy", operation, context)
        base_job.rendered_config = (base_job.rendered_config or "") + "\n!\n" + sr_cfg
        _log(
            db, wo,
            f"[SR Policy] {device.name}: segment-list "
            f"{' -> '.join(str(s) for s in context['path_segments'])}",
            actor=actor,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        _log(db, wo, f"SR Policy render skipped on {device.name}: {exc}",
             level="warning", actor=actor)
        return True


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

    # Split endpoints into controller-delegated (by site) and direct device push.
    controller_groups: dict[int, list[CircuitEndpoint]] = {}
    direct_targets: list[tuple[CircuitEndpoint | None, Device]] = []
    for ep in circuit.endpoints:
        if not ep.device:
            continue
        site = ep.device.site
        if site and site.delivery_mode == DeliveryMode.CONTROLLER and site.controller_id:
            controller_groups.setdefault(site.controller_id, []).append(ep)
        else:
            direct_targets.append((ep, ep.device))

    # For DCI services, also program the DCI gateways (direct-mode only).
    gateway_devices: list[Device] = []
    if service_type in (ServiceType.DCI, ServiceType.REMOTE_IPT) or wo.type == WorkOrderType.PROVISION:
        for gw in _dci_gateways(db, circuit):
            if gw.site and gw.site.delivery_mode == DeliveryMode.CONTROLLER:
                continue
            gateway_devices.append(gw)

    # Remote IPT: program egress-site border for NAT / default route breakout.
    egress_borders: list[Device] = []
    if service_type == ServiceType.REMOTE_IPT and circuit.egress_site_id:
        egress_borders = list(
            db.execute(
                select(Device).where(
                    Device.site_id == circuit.egress_site_id,
                    Device.role.in_([DeviceRole.DCI_GW, DeviceRole.BORDER_LEAF]),
                )
            ).scalars().all()
        )

    failed = False

    # Controller-managed delivery.
    for controller_id, eps in controller_groups.items():
        controller = db.get(Controller, controller_id)
        if controller and controller.type == ControllerType.BUGIS:
            # Built-in Bugis SDN controller: compute EVPN control plane, then
            # program the data plane on each endpoint device via vendor drivers.
            ok = _deliver_via_bugis(db, wo, circuit, controller, eps,
                                    service_type, operation, actor)
        else:
            ok = _deliver_via_controller(db, wo, circuit, controller_id, eps,
                                         operation, actor)
        failed = failed or not ok

    for endpoint, device in direct_targets:
        ok = _render_and_push(db, wo, circuit, endpoint, device, service_type,
                              operation, actor)
        failed = failed or not ok

    for gw in gateway_devices:
        ok = _render_and_push(
            db, wo, circuit, None, gw, ServiceType.DCI,
            operation, actor, is_gateway=True,
        )
        failed = failed or not ok

    for gw in egress_borders:
        if gw in gateway_devices:
            continue
        if gw.site and gw.site.delivery_mode == DeliveryMode.CONTROLLER:
            continue
        ok = _render_and_push(
            db, wo, circuit, None, gw, ServiceType.REMOTE_IPT,
            operation, actor, is_gateway=True, is_egress=True,
        )
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
        # Auto-snapshot affected devices into configuration management.
        _snapshot_devices(db, circuit, actor)
    return wo


def _snapshot_devices(db: Session, circuit: Circuit, actor: str | None) -> None:
    from app.services import config_mgmt, port_inventory

    seen: set[int] = set()
    for ep in circuit.endpoints:
        if ep.device and ep.device_id not in seen:
            seen.add(ep.device_id)
            try:
                config_mgmt.snapshot_device(
                    db, ep.device, source="push",
                    note=f"auto after {circuit.code}", created_by=actor,
                )
                port_inventory.scan_device(db, ep.device)
            except Exception:  # noqa: BLE001
                pass


def _deliver_via_bugis(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    controller: Controller,
    endpoints: list[CircuitEndpoint],
    service_type: ServiceType,
    operation: str,
    actor: str | None,
) -> bool:
    """Built-in Bugis SDN controller: control-plane + data-plane programming."""
    # 1) Control plane: compute/withdraw EVPN routes in the controller RIB.
    job = ConfigJob(
        work_order_id=wo.id,
        device_id=endpoints[0].device_id,
        operation=operation,
        transport="controller:bugis",
        status=ConfigJobStatus.PENDING,
    )
    db.add(job)
    db.flush()
    try:
        if operation == "remove":
            result = bugis_controller.withdraw_circuit(
                db, circuit, endpoints, work_order_id=wo.id
            )
        else:
            result = bugis_controller.install_circuit(
                db, circuit, endpoints, work_order_id=wo.id
            )
        job.rendered_config = result["summary"]
        job.status = ConfigJobStatus.SUCCEEDED
        _log(
            db, wo,
            f"[Bugis SDN] {operation} VNI {circuit.vni}: "
            f"{result.get('routes_installed', result.get('routes_withdrawn', 0))} 条 EVPN 路由",
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        job.status = ConfigJobStatus.FAILED
        job.output = f"bugis controller error: {exc}"
        _log(db, wo, f"Bugis 控制器错误: {exc}", level="error", actor=actor)
        return False

    # 2) Data plane: the controller programs each endpoint device via drivers.
    ok = True
    for ep in endpoints:
        if ep.device:
            ok = _render_and_push(db, wo, circuit, ep, ep.device, service_type,
                                  operation, actor) and ok
    return ok


def _deliver_via_controller(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    controller_id: int,
    endpoints: list[CircuitEndpoint],
    operation: str,
    actor: str | None,
) -> bool:
    controller = db.get(Controller, controller_id)
    if not controller:
        _log(db, wo, f"控制器 {controller_id} 不存在", level="error", actor=actor)
        return False

    devices = {ep.device_id: (ep.device.name if ep.device else ep.device_id)
               for ep in endpoints}
    # Represent the controller delivery against the first endpoint's device.
    job = ConfigJob(
        work_order_id=wo.id,
        device_id=endpoints[0].device_id,
        operation=operation,
        transport=f"controller:{controller.type.value}",
        status=ConfigJobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    try:
        req = controller_client.build_request(
            controller, circuit, endpoints, devices, operation
        )
        job.rendered_config = req.render()
        job.status = ConfigJobStatus.RENDERED
        inverse = "remove" if operation == "apply" else "apply"
        try:
            job.rollback_config = controller_client.build_request(
                controller, circuit, endpoints, devices, inverse
            ).render()
        except Exception:
            job.rollback_config = None

        result = controller_client.deliver(controller, req, dry_run=settings.dry_run)
        job.output = result["output"]
        job.status = (
            ConfigJobStatus.DRY_RUN if result.get("dry_run") and result["success"]
            else ConfigJobStatus.SUCCEEDED if result["success"]
            else ConfigJobStatus.FAILED
        )
        _log(
            db, wo,
            f"[控制器] {controller.type.value} {controller.name}: {operation} "
            f"{circuit.service_type.value} -> {job.status.value}",
            level="info" if result["success"] else "error", actor=actor,
        )
        return result["success"]
    except Exception as exc:  # noqa: BLE001
        job.status = ConfigJobStatus.FAILED
        job.output = f"controller delivery error: {exc}"
        _log(db, wo, f"控制器下发错误: {exc}", level="error", actor=actor)
        return False


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
    is_egress: bool = False,
) -> bool:
    driver = get_driver(device.vendor)
    site = device.site
    # Use a synthetic endpoint for gateway-only jobs.
    ep = endpoint or CircuitEndpoint(
        circuit_id=circuit.id,
        device_id=device.id,
        label="GW",
        interface_name="-",
        access_mode=AccessMode.DOT1Q,
        vlan_id=circuit.vlan_id,
        gateway_ip=None,
    )
    context = _build_context(
        circuit, ep, device, site, is_egress=is_egress, is_gateway=is_gateway, db=db,
    )

    job = ConfigJob(
        work_order_id=wo.id,
        device_id=device.id,
        operation=operation,
        transport=device_management.effective_transport(device),
        status=ConfigJobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    try:
        rendered = driver.render(service_type.value, operation, context)
        job.rendered_config = rendered
        job.status = ConfigJobStatus.RENDERED
        if endpoint and operation == "apply":
            _render_sr_policy(db, wo, circuit, endpoint, device, operation, actor, job)
        elif endpoint and operation == "remove":
            _render_sr_policy(db, wo, circuit, endpoint, device, operation, actor, job)
        ctrl_dataplane.mark_rendered(
            db, circuit.id, device.id, operation, rendered
        )
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
        ctrl_dataplane.mark_applied(
            db, circuit.id, device.id, operation, job.output or "", result.success
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
