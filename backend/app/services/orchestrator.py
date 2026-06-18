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
from typing import Callable

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
from app.services import (
    controller_client,
    device_management,
    platform_settings as platform_cfg,
    validation,
)


# A registered rollback returns True when the undo succeeded.
RollbackFn = Callable[[], bool]


def _refresh_live_inventory(db: Session, circuit: Circuit) -> None:
    """Refresh per-interface S-VID usage from the cached learned snapshot.

    Pure DB work (parses the latest ``source="learn"`` snapshot) — it performs
    NO live device I/O, so it adds zero load on the switch while ensuring the
    pre-flight collision check runs against the freshest known on-box state.
    """
    from app.services import port_inventory

    seen: set[int] = set()
    for ep in circuit.endpoints:
        dev = ep.device
        if dev and dev.id not in seen:
            seen.add(dev.id)
            try:
                port_inventory.scan_device(db, dev, include_legacy=False)
            except Exception:  # noqa: BLE001
                pass


def _devices_without_baseline(db: Session, circuit: Circuit) -> list[str]:
    """Names of target devices that have no learned baseline snapshot.

    Without a baseline we cannot see unmanaged on-box services, so a push there
    could collide with / overwrite live config. Callers surface this as a
    warning so the operator can run 现网学习 first.
    """
    from app.services import config_mgmt

    missing: list[str] = []
    seen: set[int] = set()
    for ep in circuit.endpoints:
        dev = ep.device
        if not dev or dev.id in seen:
            continue
        seen.add(dev.id)
        if config_mgmt.latest_learned(db, dev.id) is None:
            missing.append(dev.name)
    return missing


def _log(db: Session, wo: WorkOrder, message: str, level: str = "info",
         actor: str | None = None) -> None:
    db.add(
        WorkOrderEvent(
            work_order_id=wo.id, level=level, message=message, actor=actor
        )
    )


def _removed_config_items(rendered: str) -> list[str]:
    """Extract the concrete teardown commands (undo / no / delete) from a
    rendered remove config so we can show the operator exactly what was
    recovered, mirroring the provisioning process log."""
    items: list[str] = []
    for raw in (rendered or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue
        low = s.lower()
        if low.startswith(("undo ", "no ", "delete ")):
            items.append(s)
    return items


def _log_teardown_details(
    db: Session, wo: WorkOrder, device: Device, rendered: str, actor: str | None,
    *, is_gateway: bool = False,
) -> None:
    """Emit a per-device 'what was removed' breakdown for a remove push."""
    items = _removed_config_items(rendered)
    tag = "[GW] " if is_gateway else ""
    if not items:
        return
    _log(
        db, wo,
        f"{tag}{device.name} 回收配置 {len(items)} 项：" + "； ".join(items),
        actor=actor,
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
    partial: bool = False,
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
        "partial": partial,
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


def _endpoint_binding_key(ep: CircuitEndpoint) -> tuple:
    mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
    return (
        ep.device_id,
        ep.interface_name,
        mode,
        ep.vlan_id,
        ep.inner_vlan_id,
    )


def _endpoint_from_payload(row: dict) -> CircuitEndpoint:
    mode = row.get("access_mode", AccessMode.DOT1Q)
    if not isinstance(mode, AccessMode):
        mode = AccessMode(mode)
    return CircuitEndpoint(
        circuit_id=row.get("circuit_id") or 0,
        device_id=row["device_id"],
        label=row.get("label", "A"),
        interface_name=row["interface_name"],
        access_mode=mode,
        vlan_id=row.get("vlan_id"),
        inner_vlan_id=row.get("inner_vlan_id"),
        gateway_ip=row.get("gateway_ip"),
        ip_address=row.get("ip_address"),
    )


def _parse_previous_endpoints(wo: WorkOrder) -> list[CircuitEndpoint]:
    if not wo.payload:
        return []
    import json

    try:
        data = json.loads(wo.payload)
    except json.JSONDecodeError:
        return []
    rows = data.get("previous_endpoints") or []
    return [_endpoint_from_payload(row) for row in rows]


def _remove_previous_endpoints(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    previous_eps: list[CircuitEndpoint],
    service_type: ServiceType,
    actor: str | None,
) -> bool:
    """Tear down old AC bindings only (keep VSI/BD) before applying new endpoints."""
    failed = False
    current_keys = {_endpoint_binding_key(ep) for ep in circuit.endpoints}
    for prev in previous_eps:
        if _endpoint_binding_key(prev) in current_keys:
            continue
        device = db.get(Device, prev.device_id)
        if not device:
            continue
        _log(
            db,
            wo,
            f"拆除旧端点 {prev.label}: {device.name} {prev.interface_name}",
            actor=actor,
        )
        ok = _render_and_push(
            db,
            wo,
            circuit,
            prev,
            device,
            service_type,
            "remove",
            actor,
            partial=True,
        )
        failed = failed or not ok
    return not failed


def execute(db: Session, wo: WorkOrder, actor: str | None = None) -> WorkOrder:
    """Render and apply configuration for a work order."""
    if wo.status not in (WorkOrderStatus.APPROVED, WorkOrderStatus.SCHEDULED):
        raise ValueError("work order must be approved before execution")

    circuit = wo.circuit

    if getattr(circuit, "adopted", False):
        from app.services import port_inventory

        wo.status = WorkOrderStatus.COMPLETED
        if wo.type == WorkOrderType.DECOMMISSION:
            circuit.status = CircuitStatus.DECOMMISSIONED
            _log(
                db,
                wo,
                "现网纳管业务拆除：仅更新平台记录，不向设备下发删除配置",
                actor=actor,
            )
        else:
            circuit.status = CircuitStatus.ACTIVE
            _log(
                db,
                wo,
                "现网纳管业务：跳过配置下发，不影响现网流量",
                actor=actor,
            )
        for ep in circuit.endpoints:
            if ep.device:
                try:
                    port_inventory.scan_device(db, ep.device)
                except Exception:  # noqa: BLE001
                    pass
        return wo

    # Pre-flight compliance validation (skip for decommission).
    if wo.type != WorkOrderType.DECOMMISSION:
        plat = platform_cfg.get_or_create(db)
        if plat.protect_live_config:
            # Refresh S-VID inventory from cached learned config (zero switch
            # load) so the collision check below sees the freshest on-box state.
            _refresh_live_inventory(db, circuit)
        issues = validation.validate_circuit(db, circuit)
        errors = [i for i in issues if i.level == "error"]
        for i in issues:
            _log(db, wo, f"预检[{i.level}] {i.code}: {i.message}",
                 level="warning" if i.level != "error" else "error", actor=actor)
        if plat.protect_live_config:
            missing = _devices_without_baseline(db, circuit)
            if missing:
                _log(
                    db, wo,
                    "现网配置保护：以下设备暂无现网学习基线，无法核对未纳管业务，"
                    "下发采用增量合并(merge)不会整体覆盖，但建议先执行『现网学习』再下发："
                    + "、".join(missing),
                    level="warning", actor=actor,
                )
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

    failed = False
    # Registered undo actions for targets that were successfully programmed, so a
    # partial failure can roll back already-applied config on the OTHER devices.
    rollbacks: list[tuple[str, "RollbackFn"]] = []
    if wo.type == WorkOrderType.MODIFY and operation == "apply":
        previous_eps = _parse_previous_endpoints(wo)
        if previous_eps:
            _log(db, wo, f"端点变更：先拆除 {len(previous_eps)} 个旧接入配置", actor=actor)
            if not _remove_previous_endpoints(
                db, wo, circuit, previous_eps, service_type, actor
            ):
                failed = True

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

    # Controller-managed delivery.
    for controller_id, eps in controller_groups.items():
        controller = db.get(Controller, controller_id)
        if controller and controller.type == ControllerType.BUGIS:
            # Built-in Bugis SDN controller: compute EVPN control plane, then
            # program the data plane on each endpoint device via vendor drivers.
            ok = _deliver_via_bugis(db, wo, circuit, controller, eps,
                                    service_type, operation, actor,
                                    rollbacks=rollbacks)
        else:
            ok = _deliver_via_controller(db, wo, circuit, controller_id, eps,
                                         operation, actor, rollbacks=rollbacks)
        failed = failed or not ok

    for endpoint, device in direct_targets:
        ok = _render_and_push(db, wo, circuit, endpoint, device, service_type,
                              operation, actor, rollbacks=rollbacks)
        failed = failed or not ok

    for gw in gateway_devices:
        ok = _render_and_push(
            db, wo, circuit, None, gw, ServiceType.DCI,
            operation, actor, is_gateway=True, rollbacks=rollbacks,
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
            rollbacks=rollbacks,
        )
        failed = failed or not ok

    if failed:
        wo.status = WorkOrderStatus.FAILED
        circuit.status = CircuitStatus.FAILED
        _log(db, wo, "Execution finished with errors", level="error", actor=actor)
        _rollback_applied(db, wo, rollbacks, actor)
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
    *,
    rollbacks: list[tuple[str, RollbackFn]] | None = None,
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
        if operation == "apply" and rollbacks is not None:
            _eps = list(endpoints)

            def _undo_bugis() -> bool:
                bugis_controller.withdraw_circuit(
                    db, circuit, _eps, work_order_id=wo.id
                )
                _log(db, wo, f"[Bugis SDN] 已回滚控制面 VNI {circuit.vni}",
                     actor=actor)
                return True

            rollbacks.append((f"Bugis SDN VNI {circuit.vni}", _undo_bugis))
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
                                  operation, actor, rollbacks=rollbacks) and ok
    return ok


def _deliver_via_controller(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    controller_id: int,
    endpoints: list[CircuitEndpoint],
    operation: str,
    actor: str | None,
    *,
    rollbacks: list[tuple[str, RollbackFn]] | None = None,
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
        inverse_req = None
        try:
            inverse_req = controller_client.build_request(
                controller, circuit, endpoints, devices, inverse
            )
            job.rollback_config = inverse_req.render()
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
        if (
            result["success"]
            and operation == "apply"
            and rollbacks is not None
            and inverse_req is not None
        ):
            _ctrl_name = controller.name
            _ctrl_type = controller.type.value

            def _undo_controller() -> bool:
                res = controller_client.deliver(
                    controller, inverse_req, dry_run=settings.dry_run
                )
                if res["success"]:
                    _log(db, wo,
                         f"[控制器] {_ctrl_type} {_ctrl_name}: 已回滚 {inverse} "
                         f"{circuit.service_type.value}", actor=actor)
                else:
                    _log(db, wo,
                         f"[控制器] {_ctrl_name} 回滚失败: {res.get('output')}",
                         level="warning", actor=actor)
                return res["success"]

            rollbacks.append((f"控制器 {_ctrl_name}", _undo_controller))
        return result["success"]
    except Exception as exc:  # noqa: BLE001
        job.status = ConfigJobStatus.FAILED
        job.output = f"controller delivery error: {exc}"
        _log(db, wo, f"控制器下发错误: {exc}", level="error", actor=actor)
        return False


def _rollback_applied(
    db: Session,
    wo: WorkOrder,
    rollbacks: list[tuple[str, RollbackFn]],
    actor: str | None,
) -> None:
    """Undo config that was already applied on healthy targets after a failure.

    Runs registered undo actions in reverse order, isolating each so one bad
    rollback does not abort the rest. The work order stays FAILED regardless.
    """
    if not rollbacks:
        return
    _log(
        db, wo,
        f"下发失败：开始回滚/清理已尝试下发的 {len(rollbacks)} 个目标的配置",
        level="warning", actor=actor,
    )
    undone = 0
    for name, undo in reversed(rollbacks):
        try:
            if undo():
                undone += 1
        except Exception as exc:  # noqa: BLE001
            _log(db, wo, f"回滚 {name} 时发生异常: {exc}",
                 level="warning", actor=actor)
    _log(
        db, wo,
        f"回滚完成：{undone}/{len(rollbacks)} 个目标的配置已撤销/清理",
        level="warning" if undone < len(rollbacks) else "info",
        actor=actor,
    )


def _register_driver_rollback(
    db: Session,
    wo: WorkOrder,
    circuit: Circuit,
    device: Device,
    service_type: ServiceType,
    rollback_config: str,
    actor: str | None,
    is_gateway: bool,
    rollbacks: list[tuple[str, RollbackFn]],
    *,
    partial_failure: bool = False,
) -> None:
    """Queue an undo (the inverse 'remove' config) for an attempted device.

    ``partial_failure`` marks devices whose apply itself failed: we still push
    the remove as best-effort cleanup of any half-applied config (VSI /
    bridge-domain / QoS) so no dirty config is left behind.
    """
    tag = "[GW] " if is_gateway else ""
    verb = "清理残留" if partial_failure else "回滚"

    def _undo() -> bool:
        driver = get_driver(device.vendor)
        result = driver.push(device, rollback_config, dry_run=settings.dry_run)
        ctrl_dataplane.mark_applied(
            db, circuit.id, device.id, "remove", result.output or "", result.success
        )
        if result.success:
            _log(
                db, wo,
                f"{tag}已{verb} {device.vendor.value} {device.name}: remove "
                f"{service_type.value}",
                actor=actor,
            )
        else:
            _log(
                db, wo,
                f"{tag}{verb} {device.name} 失败: {result.output}",
                level="warning", actor=actor,
            )
        return result.success

    rollbacks.append((device.name, _undo))


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
    *,
    partial: bool = False,
    rollbacks: list[tuple[str, RollbackFn]] | None = None,
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
        partial=partial,
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
        # Teardown process detail: list exactly which config was recovered, so a
        # decommission shows a clear step-by-step like provisioning does.
        if operation == "remove" and result.success:
            _log_teardown_details(
                db, wo, device, rendered, actor, is_gateway=is_gateway
            )
        # Register cleanup for ANY apply attempt (success OR failure): a failed
        # push may have partially applied (e.g. bridge-domain/VSI created before
        # the erroring command), so on overall rollback we must scrub every
        # attempted device to avoid leaving dirty config behind.
        if (
            operation == "apply"
            and rollbacks is not None
            and job.rollback_config
        ):
            _register_driver_rollback(
                db, wo, circuit, device, service_type, job.rollback_config,
                actor, is_gateway, rollbacks, partial_failure=not result.success,
            )
        return result.success
    except Exception as exc:  # noqa: BLE001
        job.status = ConfigJobStatus.FAILED
        job.output = f"render/push error: {exc}"
        _log(db, wo, f"{device.name}: error {exc}", level="error", actor=actor)
        return False
