"""Device & interface management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, noload

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.drivers import get_driver
from app.models.device import Device, DeviceInterface
from app.models.enums import DeviceStatus, Vendor
from app.models.user import User
from app.schemas.device import (
    DeviceCreate,
    DeviceInterfaceCreate,
    DeviceInterfaceOut,
    DeviceListOut,
    DeviceOut,
    DevicePortBindingsOut,
    DeviceUpdate,
)
from app.schemas.pagination import PaginatedResponse, paginate_query, paginated
from app.services import baseline, config_learn, config_mgmt, port_inventory, snmp, snmp_settings as snmp_cfg
from app.services import device_management, platform_settings as platform_cfg

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


@router.post("", response_model=DeviceListOut, status_code=201)
def create_device(
    payload: DeviceCreate,
    learn: bool | None = Query(default=None, description="导入后立即现网配置学习；省略则跟随平台设置"),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    device = Device(**_normalize_snmp_fields(payload.model_dump()))
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
    if should_learn:
        config_learn.learn_device(db, device, created_by=user.username)
    db.commit()
    db.refresh(device)
    return device


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
    for k, v in _normalize_snmp_fields(payload.model_dump(exclude_unset=True)).items():
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
    db.delete(device)
    db.commit()


@router.post("/{device_id}/check")
def check_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Probe device reachability (NETCONF/SSH hello). Simulated in dry-run."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")

    probe = device_management.probe_reachability(db, device)
    reachable = probe["reachable"]
    latency = probe.get("latency_ms")
    transport = device_management.effective_transport(device)
    device.status = DeviceStatus.ONLINE if reachable else DeviceStatus.OFFLINE
    svid_scan: dict | None = None
    if reachable:
        svid_scan = port_inventory.scan_device(db, device)
        cfg = snmp_cfg.get_or_create(db)
        if cfg.auto_discover_on_check:
            snmp.discover_interfaces(db, device)
    db.commit()
    return {
        "device": device.name,
        "mgmt_ip": device.mgmt_ip,
        "mgmt_ip_backup": device.mgmt_ip_backup,
        "mgmt_ip_primary_label": device.mgmt_ip_primary_label or "管理网",
        "mgmt_ip_backup_label": device.mgmt_ip_backup_label or "公网",
        "mgmt_ip_active": device.mgmt_ip_active,
        "mgmt_ip_active_role": device.mgmt_ip_active_role,
        "mgmt_ip_active_label": (
            (device.mgmt_ip_primary_label or "管理网")
            if device.mgmt_ip_active_role == "primary"
            else (device.mgmt_ip_backup_label or "公网")
            if device.mgmt_ip_active_role == "backup"
            else None
        ),
        "transport": transport,
        "reachable": reachable,
        "latency_ms": latency,
        "method": probe.get("method"),
        "probes": probe.get("probes") or [],
        "status": device.status.value,
        "dry_run": settings.dry_run,
        "last_reachability_at": device.last_reachability_at,
        "svid_scan": svid_scan,
    }


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
        try:
            device_management.ensure_reachable_mgmt_ip(db, device)
        except device_management.MgmtUnreachableError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        try:
            device_management.ensure_reachable_mgmt_ip(db, device)
        except device_management.MgmtUnreachableError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
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
    return sorted(all_ifaces, key=lambda i: (i.ifindex or 0, i.name))


@router.post("/{device_id}/learn")
def learn_device_config(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Pull live running-config, parse inventory, snapshot and refresh port S-VID."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    result = config_learn.learn_device(db, device, created_by=user.username)
    db.commit()
    return result


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
