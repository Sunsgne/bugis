"""Configuration management API: device running-config, snapshots, diff."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.config_snapshot import DeviceConfigSnapshot
from app.models.device import Device
from app.models.user import User
from app.services import config_learn, config_mgmt

router = APIRouter()


@router.get("/devices")
def list_device_configs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """All devices with a summary of their latest config snapshot."""
    devices = db.execute(select(Device).order_by(Device.id)).scalars().all()
    out = []
    for d in devices:
        latest = db.execute(
            select(DeviceConfigSnapshot)
            .where(DeviceConfigSnapshot.device_id == d.id)
            .order_by(DeviceConfigSnapshot.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        learned = config_mgmt.latest_learned(db, d.id)
        state = config_learn.learned_state(db, d)
        out.append({
            "device_id": d.id,
            "name": d.name,
            "vendor": d.vendor.value,
            "role": d.role.value,
            "site_id": d.site_id,
            "latest_version": latest.version if latest else 0,
            "latest_at": latest.created_at.isoformat() if latest and latest.created_at else None,
            "latest_source": latest.source if latest else None,
            "learned_version": learned.version if learned else 0,
            "learned_at": learned.created_at.isoformat() if learned and learned.created_at else None,
            "service_count": (state.get("inventory") or {}).get("service_count", 0),
            "drift_line_count": state.get("drift_line_count", 0),
        })
    return out


@router.get("/devices/{device_id}/running")
def running_config(
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return {"device": device.name, "content": config_mgmt.build_running_config(db, device)}


@router.post("/devices/{device_id}/backup")
def backup_config(
    device_id: int,
    note: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    snap = config_mgmt.snapshot_device(db, device, source="backup", note=note,
                                       created_by=user.username)
    db.commit()
    return {"device": device.name, "version": snap.version, "id": snap.id}


@router.get("/devices/{device_id}/snapshots")
def list_snapshots(
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    rows = db.execute(
        select(DeviceConfigSnapshot)
        .where(DeviceConfigSnapshot.device_id == device_id)
        .order_by(DeviceConfigSnapshot.version.desc())
    ).scalars().all()
    return [
        {
            "id": s.id, "version": s.version, "source": s.source,
            "note": s.note, "created_by": s.created_by,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "lines": len((s.content or "").splitlines()),
        }
        for s in rows
    ]


@router.get("/devices/{device_id}/snapshots/{snap_id}")
def get_snapshot(
    device_id: int, snap_id: int,
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    snap = db.get(DeviceConfigSnapshot, snap_id)
    if not snap or snap.device_id != device_id:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return {"id": snap.id, "version": snap.version, "content": snap.content}


@router.get("/devices/{device_id}/diff")
def diff_config(
    device_id: int,
    a: int | None = None,
    b: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Diff two snapshots (defaults to the two most recent)."""
    snaps = db.execute(
        select(DeviceConfigSnapshot)
        .where(DeviceConfigSnapshot.device_id == device_id)
        .order_by(DeviceConfigSnapshot.version.desc())
    ).scalars().all()
    if not snaps:
        raise HTTPException(status_code=404, detail="no snapshots")
    by_id = {s.id: s for s in snaps}
    if a and b:
        snap_a, snap_b = by_id.get(a), by_id.get(b)
    else:
        snap_b = snaps[0]
        snap_a = snaps[1] if len(snaps) > 1 else None
    if not snap_b:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return {
        "from": snap_a.version if snap_a else None,
        "to": snap_b.version,
        "diff": config_mgmt.diff_snapshots(snap_a, snap_b) or "(无差异)",
    }


@router.get("/devices/{device_id}/drift")
def config_drift(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Diff platform-assembled running config vs latest learned live config."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    learned = config_mgmt.latest_learned(db, device_id)
    if not learned:
        raise HTTPException(status_code=404, detail="尚未执行现网配置学习")
    diff = config_mgmt.diff_platform_vs_learned(db, device)
    state = config_learn.learned_state(db, device)
    return {
        "device": device.name,
        "learned_version": learned.version,
        "inventory": state.get("inventory"),
        "diff": diff or "(无差异)",
    }
