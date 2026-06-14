"""Device & interface management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor
from app.models.user import User
from app.schemas.device import (
    DeviceCreate,
    DeviceInterfaceCreate,
    DeviceInterfaceOut,
    DeviceOut,
    DeviceUpdate,
)

router = APIRouter()


@router.get("", response_model=list[DeviceOut])
def list_devices(
    vendor: Vendor | None = None,
    site_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Device).order_by(Device.id)
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if site_id:
        stmt = stmt.where(Device.site_id == site_id)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=DeviceOut, status_code=201)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceOut)
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
