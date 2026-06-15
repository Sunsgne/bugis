"""Device & interface management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, noload

import random

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
    DeviceUpdate,
)
from app.services import baseline, config_learn, config_mgmt, port_inventory, snmp, snmp_settings as snmp_cfg
from app.services import platform_settings as platform_cfg

router = APIRouter()


@router.get("", response_model=list[DeviceListOut])
def list_devices(
    vendor: Vendor | None = None,
    site_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Device).options(noload(Device.interfaces)).order_by(Device.id)
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if site_id:
        stmt = stmt.where(Device.site_id == site_id)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=DeviceListOut, status_code=201)
def create_device(
    payload: DeviceCreate,
    learn: bool | None = Query(default=None, description="导入后立即现网配置学习；省略则跟随平台设置"),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    device = Device(**payload.model_dump())
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
    for k, v in payload.model_dump(exclude_unset=True).items():
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

    if settings.dry_run:
        reachable = random.random() > 0.1
        latency = round(random.uniform(0.5, 12.0), 2)
    else:  # pragma: no cover - requires live device
        import socket
        reachable = False
        latency = 0.0
        try:
            with socket.create_connection(
                (device.mgmt_ip, device.netconf_port), timeout=3
            ):
                reachable = True
        except OSError:
            reachable = False

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
        "transport": "netconf",
        "reachable": reachable,
        "latency_ms": latency,
        "status": device.status.value,
        "dry_run": settings.dry_run,
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
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device_id)
    ).scalars().all()


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
        "transport": driver.transport,
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
    ifaces = snmp.discover_interfaces(db, device)
    port_inventory.scan_device(db, device)
    db.commit()
    return sorted(ifaces, key=lambda i: (i.ifindex or 0))


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
