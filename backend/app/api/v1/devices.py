"""Device & interface management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, noload

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.drivers import get_driver
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device, DeviceInterface
from app.models.enums import CircuitStatus, DeviceStatus, Vendor
from app.models.user import User
from app.schemas.device import (
    DeviceCreate,
    DeviceCreateOut,
    DeviceInterfaceCreate,
    DeviceInterfaceOut,
    DeviceListOut,
    DeviceOut,
    DevicePortBindingsOut,
    DeviceUpdate,
    InterfaceDescriptionBulkIn,
    InterfaceDescriptionBulkOut,
    InterfaceDescriptionMultiBulkIn,
    InterfaceDescriptionMultiBulkOut,
    DeviceLearnBatchIn,
    DeviceLearnBatchOut,
    DeviceCheckBatchIn,
    DeviceCheckBatchOut,
    DeviceCheckScheduledOut,
)
from app.schemas.pagination import PaginatedResponse, paginate_query, paginated
from app.services import baseline, config_learn, config_mgmt, port_inventory, snmp, snmp_settings as snmp_cfg
from app.services import device_management, interface_admin, platform_settings as platform_cfg
from app.services.credential_store import encrypt_device_fields

router = APIRouter()


def _normalize_snmp_fields(data: dict) -> dict:
    out = dict(data)
    for key in ("snmp_community", "snmp_v3_username"):
        if out.get(key) == "":
            out[key] = None
    for key in ("snmp_v3_auth_password", "snmp_v3_priv_password", "enable_password"):
        if out.get(key) == "":
            out.pop(key, None)
    return out


@router.get("", response_model=PaginatedResponse[DeviceListOut])
def list_devices(
    vendor: Vendor | None = None,
    site_id: int | None = None,
    q: str | None = Query(None, description="Search name, hostname or mgmt IP"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Device).options(noload(Device.interfaces)).order_by(Device.id.desc())
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if site_id:
        stmt = stmt.where(Device.site_id == site_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Device.name.ilike(like),
                Device.hostname.ilike(like),
                Device.mgmt_ip.ilike(like),
            )
        )
    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    return paginated(rows, total=total, page=page, page_size=page_size)


@router.get("/summary")
def device_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Fleet-wide status counts (not page-limited) for dashboard KPIs."""
    counts = dict(
        db.execute(
            select(Device.status, func.count(Device.id)).group_by(Device.status)
        ).all()
    )
    total = int(sum(counts.values()))
    online = int(counts.get(DeviceStatus.ONLINE, 0))
    offline = int(counts.get(DeviceStatus.OFFLINE, 0))
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "other": total - online - offline,
    }


@router.post("", response_model=DeviceCreateOut, status_code=201)
def create_device(
    payload: DeviceCreate,
    learn: bool | None = Query(default=None, description="导入后立即现网配置学习；省略则跟随平台设置"),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    device = Device(**encrypt_device_fields(_normalize_snmp_fields(payload.model_dump())))
    db.add(device)
    db.flush()
    should_learn = False
    if learn is True:
        should_learn = True
    elif learn is False:
        should_learn = False
    else:
        plat = platform_cfg.get_or_create(db)
        should_learn = plat.auto_learn_on_import
    db.commit()
    db.refresh(device)
    if should_learn:
        from app.services import concurrent_learn

        concurrent_learn.schedule_learn_device(
            device.id,
            created_by=user.username,
        )
    out = DeviceCreateOut.model_validate(device)
    out.learn_scheduled = should_learn
    return out


@router.get("/{device_id}", response_model=DeviceListOut)
def get_device(
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    device = db.execute(
        select(Device).options(noload(Device.interfaces)).where(Device.id == device_id)
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceListOut)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    for k, v in encrypt_device_fields(
        _normalize_snmp_fields(payload.model_dump(exclude_unset=True))
    ).items():
        setattr(device, k, v)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    # Block deletion while live circuits still terminate on this device —
    # removing it would orphan endpoints and leave half-provisioned circuits.
    blocking = db.scalar(
        select(func.count(Circuit.id.distinct()))
        .select_from(CircuitEndpoint)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(
            CircuitEndpoint.device_id == device_id,
            Circuit.status != CircuitStatus.DECOMMISSIONED,
        )
    ) or 0
    if blocking:
        raise HTTPException(
            status_code=409,
            detail=f"该设备仍承载 {blocking} 条未退服专线，请先退服或迁移这些专线后再删除设备",
        )
    db.delete(device)
    db.commit()


@router.post("/check-batch", response_model=DeviceCheckBatchOut)
def check_devices_batch(
    payload: DeviceCheckBatchIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Reachability + S-VID scan for multiple devices concurrently (background)."""
    if not payload.device_ids:
        raise HTTPException(status_code=400, detail="device_ids required")
    plat = platform_cfg.get_or_create(db)
    max_workers = max(1, int(plat.provision_max_concurrency or 4))
    unique = list(dict.fromkeys(payload.device_ids))
    from app.services import concurrent_device_check

    concurrent_device_check.schedule_device_checks(unique, max_workers=max_workers)
    return DeviceCheckBatchOut(
        scheduled=len(unique),
        device_ids=unique,
        max_workers=min(max_workers, len(unique)),
    )


@router.post("/{device_id}/check")
def check_device(
    device_id: int,
    background: bool = Query(
        default=True,
        description="true：后台探测+S-VID 扫描，HTTP 立即返回；false：同步等待完整结果",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Probe device reachability and refresh S-VID inventory."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    if background:
        from app.services import concurrent_device_check

        concurrent_device_check.schedule_device_check(device_id)
        return DeviceCheckScheduledOut(
            scheduled=True,
            device_id=device.id,
            device=device.name,
        )

    from app.services import device_check_service

    result = device_check_service.run_device_check(db, device_id)
    db.commit()
    return result


@router.post("/{device_id}/interfaces", response_model=DeviceInterfaceOut, status_code=201)
def add_interface(
    device_id: int,
    payload: DeviceInterfaceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    iface = DeviceInterface(device_id=device_id, **payload.model_dump())
    db.add(iface)
    db.commit()
    db.refresh(iface)
    return iface


@router.post(
    "/{device_id}/interfaces/descriptions",
    response_model=InterfaceDescriptionBulkOut,
)
def set_interface_descriptions(
    device_id: int,
    payload: InterfaceDescriptionBulkIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Bulk-update interface descriptions and (optionally) push to the device.

    Use the customer ID alone on a physical/main port (e.g. ``SDWAN-BACKBONE``)
    and ``<customer>:<circuit>`` on a service sub-interface
    (e.g. ``SDWAN-BACKBONE:CIR-DD02B7``). Honors dry-run.
    """
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if not payload.items:
        raise HTTPException(status_code=400, detail="no interfaces provided")
    if payload.push and not settings.dry_run:
        try:
            device_management.ensure_reachable_mgmt_ip(db, device)
        except device_management.MgmtUnreachableError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [(i.name, i.description) for i in payload.items]
    return interface_admin.apply_descriptions(db, device, items, push=payload.push)


@router.post(
    "/interfaces/descriptions/bulk",
    response_model=InterfaceDescriptionMultiBulkOut,
)
def bulk_set_interface_descriptions(
    payload: InterfaceDescriptionMultiBulkIn,
    _: User = Depends(require_operator),
):
    """Update and push interface descriptions on multiple devices in parallel."""
    if not payload.devices:
        raise HTTPException(status_code=400, detail="no devices provided")
    jobs = [
        (entry.device_id, [(i.name, i.description) for i in entry.items])
        for entry in payload.devices
        if entry.items
    ]
    if not jobs:
        raise HTTPException(status_code=400, detail="no interfaces provided")
    results = interface_admin.apply_descriptions_parallel(jobs, push=payload.push)
    errors = [r for r in results if r.get("error")]
    if errors and len(errors) == len(results):
        raise HTTPException(status_code=502, detail=errors[0].get("error", "push failed"))
    total_updated = sum(int(r.get("updated") or 0) for r in results)
    dry_run = bool(results[0].get("dry_run")) if results else settings.dry_run
    all_pushed = all(bool(r.get("pushed")) for r in results if not r.get("error"))
    return {
        "results": results,
        "total_updated": total_updated,
        "all_pushed": all_pushed,
        "dry_run": dry_run,
    }


@router.get("/{device_id}/interfaces", response_model=list[DeviceInterfaceOut])
def list_interfaces(
    device_id: int,
    scan: bool = Query(False, description="Refresh S-VID inventory before returning"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if scan:
        # S-VID scan reads learned/cached running-config — no live southbound probe.
        port_inventory.scan_device(db, device)
        db.commit()
    rows = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device_id)
    ).scalars().all()
    if device.vendor == Vendor.HUAWEI:
        rows = [r for r in rows if not port_inventory.is_huawei_subinterface(r.name)]
    return sorted(rows, key=lambda i: (i.ifindex or 0, i.name))


@router.get("/{device_id}/port-bindings", response_model=DevicePortBindingsOut)
def list_port_bindings(
    device_id: int,
    scan: bool = Query(False, description="Refresh S-VID inventory before building relationships"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Customer · interface · service relationship table for this device."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if scan:
        # S-VID scan reads learned/cached running-config — no live southbound probe.
        port_inventory.scan_device(db, device)
        db.commit()
    return port_inventory.list_port_bindings(db, device)


@router.get("/{device_id}/overlay-inventory")
def get_device_overlay_inventory(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Per-device VNI/VSI services from learned running-config (read-only)."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    from app.services import overlay_inventory

    return overlay_inventory.device_overlay_inventory(db, device)


@router.get("/{device_id}/baseline")
def device_baseline(
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Preview the standard initialization (baseline) config for a device."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return {"device": device.name, "vendor": device.vendor.value,
            "content": baseline.render_baseline(db, device)}


@router.post("/{device_id}/initialize")
def initialize_device(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Render + (dry-run) push the baseline config and snapshot it as 'init'."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    config = baseline.render_baseline(db, device)
    driver = get_driver(device.vendor)
    result = driver.push(device, config, dry_run=settings.dry_run)
    snap = config_mgmt.add_snapshot(
        db, device, config, source="init",
        note="device initialization", created_by=user.username,
    )
    if device.status == DeviceStatus.UNKNOWN:
        device.status = DeviceStatus.ONLINE
    db.commit()
    return {
        "device": device.name,
        "transport": device_management.effective_transport(device),
        "dry_run": result.dry_run,
        "success": result.success,
        "version": snap.version,
        "content": config,
    }


@router.post("/{device_id}/discover-interfaces", response_model=list[DeviceInterfaceOut])
def discover_interfaces(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Discover the device's interfaces via SNMP (IF-MIB) and persist them."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    from app.services import snmp_device

    cfg = snmp_device.effective_snmp(device)
    if not cfg["enabled"]:
        raise HTTPException(status_code=400, detail="该设备未启用 SNMP，请在设备设置中开启")
    try:
        ifaces = snmp.discover_interfaces(db, device)
    except device_management.MgmtUnreachableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (RuntimeError, ImportError, ModuleNotFoundError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    port_inventory.scan_device(db, device)
    db.commit()
    all_ifaces = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    if device.vendor == Vendor.HUAWEI:
        all_ifaces = [r for r in all_ifaces if not port_inventory.is_huawei_subinterface(r.name)]
    return sorted(all_ifaces, key=lambda i: (i.ifindex or 0, i.name))


@router.get("/credential-audit")
def credential_audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """List devices whose southbound credentials are missing or cannot be decrypted."""
    from app.services import credential_audit_service

    return credential_audit_service.audit_all_devices(db)


@router.post("/learn-batch", response_model=DeviceLearnBatchOut)
def learn_devices_batch(
    payload: DeviceLearnBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Pull running-config from multiple devices concurrently (thread pool)."""
    if not payload.device_ids:
        raise HTTPException(status_code=400, detail="device_ids required")
    plat = platform_cfg.get_or_create(db)
    max_workers = payload.max_workers
    if max_workers is None:
        max_workers = max(1, int(plat.provision_max_concurrency or 4))
    else:
        max_workers = max(1, min(16, max_workers))

    summary = config_learn.learn_devices_batch(
        db,
        payload.device_ids,
        created_by=user.username,
        max_workers=max_workers,
    )
    return DeviceLearnBatchOut(**summary)


@router.post("/{device_id}/learn")
def learn_device_config(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Queue live config learn; poll GET /devices/{id}/learned-state for phase progress."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    run_id = config_learn.start_learn_device(db, device, created_by=user.username)
    db.commit()
    return {
        "scheduled": True,
        "device_id": device.id,
        "device": device.name,
        "run_id": run_id,
        "phase": "reachability",
    }


@router.get("/{device_id}/learned-state")
def get_learned_state(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return config_learn.learned_state(db, device)
