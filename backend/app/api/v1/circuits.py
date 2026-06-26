"""Circuit (专线) management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
import difflib

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.config_job import ConfigJob
from app.models.device import Device
from app.models.enums import CircuitStatus, PathMode, AccessMode, ServiceType
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workorder import WorkOrder
from app.schemas.circuit import (
    CircuitAdoptCreate,
    CircuitAdoptVniCreate,
    CircuitAdoptVniPreview,
    CircuitCreate,
    CircuitDeleteScheduledOut,
    CircuitEndpointCreate,
    CircuitEndpointOut,
    CircuitEndpointsReplace,
    CircuitEndpointUpdate,
    CircuitListOut,
    CircuitOut,
    CircuitPathHopSchema,
    CircuitUpdate,
)
from app.schemas.pagination import PaginatedResponse, paginate_query, paginated
from app.schemas.forwarding_path import ForwardingPathResponse
from app.schemas.path import PathPreviewRequest, PathPreviewResponse
from app.services import allocation, circuit_adopt, concurrent_scan, forwarding_path_service, link_planner, path_service, port_inventory, probe, validation
from app.services import platform_settings as platform_cfg
from app.services.circuit_alarm_settings import thresholds_out

router = APIRouter()

DELETABLE_STATUSES = frozenset({
    CircuitStatus.DECOMMISSIONED,
    CircuitStatus.DRAFT,
    CircuitStatus.FAILED,
})


def _site_asn_for_endpoints(db: Session, endpoints: list[CircuitEndpoint]) -> int | None:
    for ep in endpoints:
        device = db.get(Device, ep.device_id)
        if device and device.bgp_asn:
            return device.bgp_asn
        if device and device.site and device.site.bgp_asn:
            return device.site.bgp_asn
    return None


def _endpoint_out(db: Session, ep: CircuitEndpoint) -> CircuitEndpointOut:
    base = CircuitEndpointOut.model_validate(ep, from_attributes=True)
    desc = (ep.interface_description or "").strip() or None
    if not desc and ep.device_id and ep.interface_name:
        desc = link_planner._interface_description(db, ep.device_id, ep.interface_name)
    if desc != base.interface_description:
        return base.model_copy(update={"interface_description": desc})
    return base


def _endpoints_out(db: Session, circuit: Circuit) -> list[CircuitEndpointOut]:
    return [_endpoint_out(db, ep) for ep in circuit.endpoints]


def _to_circuit_list_out(db: Session, circuit: Circuit) -> CircuitListOut:
    base = CircuitListOut.model_validate(circuit, from_attributes=True)
    plat = platform_cfg.get_or_create(db)
    return base.model_copy(
        update={
            **thresholds_out(circuit, plat),
            "endpoints": _endpoints_out(db, circuit),
        }
    )


def _to_circuit_out(db: Session, circuit: Circuit) -> CircuitOut:
    path_devices = path_service.full_path_for_circuit(db, circuit)
    hop_schemas = []
    for h in sorted(circuit.path_hops, key=lambda x: x.sequence):
        dev = h.device or db.get(Device, h.device_id)
        hop_schemas.append(
            CircuitPathHopSchema(
                device_id=h.device_id,
                sequence=h.sequence,
                device_name=dev.name if dev else None,
                overlay_tech=dev.overlay_tech.value if dev else None,
                sr_node_sid=dev.sr_node_sid if dev else None,
            )
        )
    base = CircuitOut.model_validate(circuit, from_attributes=True)
    plat = platform_cfg.get_or_create(db)
    return base.model_copy(
        update={
            **thresholds_out(circuit, plat),
            "path_hops": hop_schemas,
            "segment_list": path_service.segment_list(path_devices),
            "endpoints": _endpoints_out(db, circuit),
        }
    )


@router.post("/path/preview", response_model=PathPreviewResponse)
def preview_path(
    payload: PathPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data = path_service.preview_path(
        db,
        payload.endpoint_device_ids,
        payload.via_device_ids,
        payload.path_mode,
    )
    return PathPreviewResponse(**data)


@router.get("", response_model=PaginatedResponse[CircuitListOut])
def list_circuits(
    tenant_id: int | None = None,
    q: str | None = Query(None, description="Search code or name"),
    status: CircuitStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Circuit).order_by(Circuit.id.desc())
    if tenant_id:
        stmt = stmt.where(Circuit.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(Circuit.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Circuit.code.ilike(like), Circuit.name.ilike(like)))
    circuits, total = paginate_query(db, stmt, page=page, page_size=page_size)
    return paginated(
        [_to_circuit_list_out(db, c) for c in circuits],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CircuitOut, status_code=201)
def create_circuit(
    payload: CircuitCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if not db.get(Tenant, payload.tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")

    data = payload.model_dump(
        exclude={"endpoints", "code", "via_device_ids"}
    )
    via_ids = payload.via_device_ids or []
    path_mode = payload.path_mode
    if via_ids and path_mode == PathMode.AUTO:
        path_mode = PathMode.EXPLICIT_SR

    endpoint_ids = [ep.device_id for ep in payload.endpoints]
    if path_mode == PathMode.EXPLICIT_SR:
        preview = path_service.preview_path(db, endpoint_ids, via_ids, path_mode)
        if not preview["explicit_supported"]:
            raise HTTPException(status_code=400, detail=preview["reason"])
        if preview["connectivity_errors"]:
            raise HTTPException(
                status_code=400,
                detail="; ".join(preview["connectivity_errors"]),
            )
    data["path_mode"] = path_mode

    circuit = Circuit(**data)
    circuit.code = payload.code or allocation.next_circuit_code(db)

    if circuit.vni is not None:
        if not (validation.VNI_MIN <= circuit.vni <= validation.VNI_MAX):
            raise HTTPException(status_code=400, detail=f"VNI {circuit.vni} 超出有效范围")
        vni_msg = allocation.vni_unavailable_message(db, circuit.vni)
        if vni_msg:
            raise HTTPException(status_code=409, detail=vni_msg)

    if circuit.vsi_name:
        circuit.vsi_name = allocation.normalize_vsi_name(circuit.vsi_name)
        vsi_msg = allocation.vsi_unavailable_message(db, circuit.vsi_name)
        if vsi_msg:
            raise HTTPException(status_code=409, detail=vsi_msg)

    db.add(circuit)
    db.flush()

    endpoints: list[CircuitEndpoint] = []
    for ep in payload.endpoints:
        if not db.get(Device, ep.device_id):
            raise HTTPException(
                status_code=404, detail=f"device {ep.device_id} not found"
            )
        endpoint = CircuitEndpoint(circuit_id=circuit.id, **ep.model_dump())
        db.add(endpoint)
        endpoints.append(endpoint)
    db.flush()

    asn = _site_asn_for_endpoints(db, endpoints)
    allocation.auto_allocate_circuit_fields(db, circuit, asn)
    if via_ids:
        path_service.save_path_hops(db, circuit, via_ids)

    for ep in endpoints:
        svid = ep.vlan_id or circuit.vlan_id
        mode = ep.access_mode or AccessMode.DOT1Q
        ok, msg = port_inventory.check_endpoint_available(
            db,
            ep.device_id,
            ep.interface_name,
            svid,
            ep.inner_vlan_id,
            mode,
            exclude_circuit_id=circuit.id,
        )
        if not ok:
            raise HTTPException(status_code=409, detail=msg)

    db.commit()
    db.refresh(circuit)
    return _to_circuit_out(db, circuit)


@router.get("/adopt-by-vni/preview", response_model=CircuitAdoptVniPreview)
def preview_adopt_by_vni(
    vni: int = Query(..., ge=1),
    device_ids: str | None = Query(
        None, description="Comma-separated device IDs to limit discovery"
    ),
    refresh_inventory: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Preview endpoints discovered for a VNI from whole-network learned config."""
    parsed_ids: list[int] | None = None
    if device_ids:
        parsed_ids = [int(part.strip()) for part in device_ids.split(",") if part.strip()]
    data = circuit_adopt.preview_adopt_by_vni(
        db,
        vni,
        device_ids=parsed_ids,
        refresh_inventory=refresh_inventory,
    )
    return CircuitAdoptVniPreview(**data)


@router.post("/adopt-from-vni", response_model=CircuitOut, status_code=201)
def adopt_circuit_from_vni(
    payload: CircuitAdoptVniCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Adopt an on-box VNI service by auto-associating learned devices and interfaces."""
    circuit = circuit_adopt.adopt_circuit_from_vni(
        db, payload, created_by=user.username
    )
    db.commit()
    db.refresh(circuit)
    return _to_circuit_out(db, circuit)


@router.post("/adopt-from-inventory", response_model=CircuitOut, status_code=201)
def adopt_circuit_from_inventory(
    payload: CircuitAdoptCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Register an on-box S-VID binding as a managed circuit without pushing config."""
    circuit = circuit_adopt.adopt_circuit_from_inventory(
        db, payload, created_by=user.username
    )
    db.commit()
    db.refresh(circuit)
    return _to_circuit_out(db, circuit)


@router.get("/{circuit_id}", response_model=CircuitOut)
def get_circuit(
    circuit_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return _to_circuit_out(db, circuit)


@router.get("/{circuit_id}/path", response_model=PathPreviewResponse)
def get_circuit_path(
    circuit_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    endpoint_ids = [ep.device_id for ep in circuit.endpoints]
    via_ids = [h.device_id for h in sorted(circuit.path_hops, key=lambda h: h.sequence)]
    data = path_service.preview_path(db, endpoint_ids, via_ids, circuit.path_mode)
    return PathPreviewResponse(**data)


@router.get("/{circuit_id}/forwarding-path", response_model=ForwardingPathResponse)
def get_forwarding_path(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Business (EVPN) + control-plane RIB + underlay (IGP cost + probe) path view."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return ForwardingPathResponse(**forwarding_path_service.build_forwarding_path(db, circuit))


@router.get("/{circuit_id}/validate")
def validate_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run pre-flight compliance checks on a circuit."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return validation.summarize(validation.validate_circuit(db, circuit))


def _circuit_jobs(db: Session, circuit_id: int) -> list[tuple[ConfigJob, str]]:
    rows = db.execute(
        select(ConfigJob, WorkOrder.code)
        .join(WorkOrder, WorkOrder.id == ConfigJob.work_order_id)
        .where(WorkOrder.circuit_id == circuit_id)
        .order_by(ConfigJob.id)
    ).all()
    return [(row[0], row[1]) for row in rows]


@router.post("/{circuit_id}/probe")
def probe_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Run an on-demand end-to-end path probe (records a telemetry sample)."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if not circuit.latency_probe_enabled:
        raise HTTPException(status_code=400, detail="该专线已关闭延迟探测")
    result = probe.probe_circuit(db, circuit)
    from app.services import probe_log_service

    log = probe_log_service.save_probe_log(db, circuit, result)
    db.commit()
    return {**result, "probe_log_id": log.id}


@router.get("/{circuit_id}/probe/latest")
def latest_probe(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the most recent persisted probe result (frontend reads DB only)."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    from app.services import probe_log_service

    row = probe_log_service.latest_probe_log(db, circuit_id)
    if not row:
        raise HTTPException(status_code=404, detail="no probe history")
    return row.result_json or {
        "circuit": circuit.code,
        "mode": row.mode,
        "probe_method": row.probe_method,
        "reachable": row.reachable,
        "rtt_ms": row.rtt_ms,
        "jitter_ms": row.jitter_ms,
        "packet_loss_pct": row.packet_loss_pct,
        "path_mode": row.path_mode,
        "probe_log_id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/{circuit_id}/probe/history")
def probe_history(
    circuit_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    from app.services import probe_log_service

    rows = probe_log_service.list_probe_logs(db, circuit_id, limit=limit)
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "mode": r.mode,
            "probe_method": r.probe_method,
            "reachable": r.reachable,
            "rtt_ms": r.rtt_ms,
            "jitter_ms": r.jitter_ms,
            "packet_loss_pct": r.packet_loss_pct,
            "path_mode": r.path_mode,
        }
        for r in rows
    ]


@router.get("/{circuit_id}/config-history")
def config_history(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Per-device timeline of rendered configuration versions."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    device_names = {d.id: d.name for d in db.execute(select(Device)).scalars().all()}
    history: dict[int, dict] = {}
    for job, wo_code in _circuit_jobs(db, circuit_id):
        entry = history.setdefault(
            job.device_id,
            {"device_id": job.device_id,
             "device": device_names.get(job.device_id, job.device_id),
             "versions": []},
        )
        entry["versions"].append({
            "job_id": job.id,
            "work_order": wo_code,
            "operation": job.operation,
            "status": job.status.value,
            "transport": job.transport,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "rendered_config": job.rendered_config,
        })
    return {"circuit": circuit.code, "devices": list(history.values())}


@router.get("/{circuit_id}/config-diff")
def config_diff(
    circuit_id: int,
    device_id: int,
    a: int | None = None,
    b: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Unified diff between two config versions of a device on this circuit.

    Defaults to the two most recent versions when a/b are not given.
    """
    if not db.get(Circuit, circuit_id):
        raise HTTPException(status_code=404, detail="circuit not found")
    jobs = [j for j, _wo in _circuit_jobs(db, circuit_id) if j.device_id == device_id]
    if len(jobs) < 1:
        raise HTTPException(status_code=404, detail="no config versions for device")

    def _by_id(jid: int) -> ConfigJob | None:
        return next((j for j in jobs if j.id == jid), None)

    if a and b:
        job_a, job_b = _by_id(a), _by_id(b)
    elif len(jobs) >= 2:
        job_a, job_b = jobs[-2], jobs[-1]
    else:
        job_a, job_b = None, jobs[-1]
    if not job_b:
        raise HTTPException(status_code=404, detail="version not found")

    left = (job_a.rendered_config or "") if job_a else ""
    right = job_b.rendered_config or ""
    diff = "\n".join(
        difflib.unified_diff(
            left.splitlines(), right.splitlines(),
            fromfile=f"job-{job_a.id}" if job_a else "empty",
            tofile=f"job-{job_b.id}",
            lineterm="",
        )
    )
    return {
        "device_id": device_id,
        "from_job": job_a.id if job_a else None,
        "to_job": job_b.id,
        "changed": left != right,
        "diff": diff or "(无差异 / no changes)",
    }


@router.patch("/{circuit_id}", response_model=CircuitOut)
def update_circuit(
    circuit_id: int,
    payload: CircuitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(circuit, k, v)
    db.commit()
    db.refresh(circuit)
    return _to_circuit_out(db, circuit)


@router.get("/{circuit_id}/preview")
def preview_circuit_config(
    circuit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Render (dry-run) the provisioning config WITHOUT creating a work order.

    Repeated previews must not pollute the work-order list, so this renders
    in-memory only.
    """
    from app.drivers import get_driver

    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    previews = []
    for ep in circuit.endpoints:
        device = ep.device
        if not device:
            continue
        driver = get_driver(device.vendor)
        context = {
            "circuit": circuit,
            "endpoint": ep,
            "device": device,
            "site": device.site,
        }
        previews.append(
            {
                "device": device.name,
                "vendor": device.vendor.value,
                "transport": driver.transport,
                "config": driver.render(circuit.service_type.value, "apply", context),
            }
        )
    return {"operation": "apply", "previews": previews}


@router.delete(
    "/{circuit_id}",
    responses={
        204: {"description": "Circuit deleted"},
        202: {"model": CircuitDeleteScheduledOut},
    },
)
def delete_circuit(
    circuit_id: int,
    background: bool = Query(
        default=False,
        description="true：后台删除记录，HTTP 立即返回；false：同步等待删除完成",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    from app.services import circuit_delete_service, concurrent_circuit_delete

    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if circuit.status not in DELETABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "仅已拆除、草稿或失败状态的专线可删除；"
                "请先执行拆除工单后再删除"
            ),
        )
    if background:
        code = circuit.code
        concurrent_circuit_delete.schedule_circuit_delete(circuit_id)
        body = CircuitDeleteScheduledOut(
            scheduled=True,
            circuit_id=circuit_id,
            circuit_code=code,
        )
        return JSONResponse(status_code=202, content=body.model_dump())
    circuit_delete_service.delete_circuit_record(db, circuit)
    db.commit()
    return Response(status_code=204)


@router.put("/{circuit_id}/endpoints", response_model=CircuitOut)
def replace_endpoints(
    circuit_id: int,
    payload: CircuitEndpointsReplace,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Replace all attachment endpoints on a circuit (for port / VLAN changes)."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")

    min_eps = 1 if circuit.service_type == ServiceType.REMOTE_IPT else 2
    if len(payload.endpoints) < min_eps:
        raise HTTPException(
            status_code=400,
            detail=f"至少需要 {min_eps} 个端点",
        )

    for ep in payload.endpoints:
        if not db.get(Device, ep.device_id):
            raise HTTPException(status_code=404, detail=f"device {ep.device_id} not found")

    adopt_rows: dict[int, dict] = {}
    if circuit.adopted:
        adopt_rows = circuit_adopt.validate_adopted_endpoints_replace(
            db, circuit, payload.endpoints
        )
    else:
        for ep in payload.endpoints:
            svid = ep.vlan_id or circuit.vlan_id
            mode = ep.access_mode or AccessMode.DOT1Q
            ok, msg = port_inventory.check_endpoint_available(
                db,
                ep.device_id,
                ep.interface_name,
                svid,
                ep.inner_vlan_id,
                mode,
                exclude_circuit_id=circuit.id,
            )
            if not ok:
                raise HTTPException(status_code=409, detail=msg)

    old_by_key: dict[tuple, CircuitEndpoint] = {}
    for old_ep in circuit.endpoints:
        mode = old_ep.access_mode or AccessMode.DOT1Q
        svid = old_ep.vlan_id or circuit.vlan_id
        key = circuit_adopt._endpoint_tuple(
            old_ep.device_id,
            old_ep.interface_name,
            mode,
            svid,
            old_ep.inner_vlan_id,
        )
        old_by_key[key] = old_ep

    for old in list(circuit.endpoints):
        db.delete(old)
    db.flush()

    new_endpoints: list[CircuitEndpoint] = []
    for idx, ep in enumerate(payload.endpoints):
        mode = ep.access_mode or AccessMode.DOT1Q
        svid = ep.vlan_id or circuit.vlan_id
        key = circuit_adopt._endpoint_tuple(
            ep.device_id, ep.interface_name, mode, svid, ep.inner_vlan_id
        )
        prev = old_by_key.get(key)
        adopt_row = adopt_rows.get(idx)
        endpoint = CircuitEndpoint(
            circuit_id=circuit.id,
            interface_description=(
                prev.interface_description
                if prev
                else (adopt_row.get("description") if adopt_row else None)
            ),
            **ep.model_dump(),
        )
        db.add(endpoint)
        new_endpoints.append(endpoint)
    db.flush()

    if circuit.path_mode == PathMode.EXPLICIT_SR:
        endpoint_ids = [ep.device_id for ep in new_endpoints]
        via_ids = [h.device_id for h in sorted(circuit.path_hops, key=lambda h: h.sequence)]
        preview = path_service.preview_path(db, endpoint_ids, via_ids, circuit.path_mode)
        if preview.get("connectivity_errors"):
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="; ".join(preview["connectivity_errors"]),
            )

    db.commit()
    db.refresh(circuit)
    concurrent_scan.scan_devices_parallel(
        [ep.device_id for ep in new_endpoints],
        include_legacy=False,
    )
    from app.controller import controller as bugis_controller

    bugis_controller.sync_circuit_overlay(db, circuit)
    db.commit()
    db.refresh(circuit)
    return _to_circuit_out(db, circuit)


@router.patch("/{circuit_id}/endpoints/{endpoint_id}", response_model=CircuitEndpointOut)
def update_endpoint(
    circuit_id: int,
    endpoint_id: int,
    payload: CircuitEndpointUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    endpoint = db.get(CircuitEndpoint, endpoint_id)
    if not endpoint or endpoint.circuit_id != circuit_id:
        raise HTTPException(status_code=404, detail="endpoint not found")

    data = payload.model_dump()
    if not db.get(Device, data["device_id"]):
        raise HTTPException(status_code=404, detail="device not found")

    svid = data.get("vlan_id") or circuit.vlan_id
    mode = data.get("access_mode") or AccessMode.DOT1Q
    ok, msg = port_inventory.check_endpoint_available(
        db,
        data["device_id"],
        data["interface_name"],
        svid,
        data.get("inner_vlan_id"),
        mode,
        exclude_circuit_id=circuit.id,
    )
    if not ok:
        raise HTTPException(status_code=409, detail=msg)

    for k, v in data.items():
        setattr(endpoint, k, v)
    db.commit()
    db.refresh(endpoint)
    return _endpoint_out(db, endpoint)


@router.post(
    "/{circuit_id}/endpoints", response_model=CircuitEndpointOut, status_code=201
)
def add_endpoint(
    circuit_id: int,
    payload: CircuitEndpointCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if not db.get(Device, payload.device_id):
        raise HTTPException(status_code=404, detail="device not found")
    endpoint = CircuitEndpoint(circuit_id=circuit_id, **payload.model_dump())
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return _endpoint_out(db, endpoint)


@router.delete("/{circuit_id}/endpoints/{endpoint_id}", status_code=204)
def delete_endpoint(
    circuit_id: int,
    endpoint_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    endpoint = db.get(CircuitEndpoint, endpoint_id)
    if not endpoint or endpoint.circuit_id != circuit_id:
        raise HTTPException(status_code=404, detail="endpoint not found")
    db.delete(endpoint)
    db.commit()
