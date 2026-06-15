"""SNMP settings API."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core.database import get_db
from app.models.device import Device
from app.models.enums import DeviceRole, DeviceStatus, OverlayTech, Vendor
from app.models.user import User
from app.schemas.snmp_settings import (
    SnmpSettingsOut,
    SnmpSettingsUpdate,
    SnmpTestRequest,
    SnmpTestResponse,
)
from app.services import snmp, snmp_settings

router = APIRouter()


@router.get("/mibs")
def list_snmp_mibs(_: User = Depends(get_current_user)):
    """Bundled IETF MIB files and OIDs used for IF-MIB walks."""
    from app.services.mib_registry import IF_MIB, list_bundled_mibs

    return {
        "manifest": list_bundled_mibs(),
        "oids_in_use": [
            {"symbol": o.symbol, "oid": o.oid, "mib": o.mib, "rfc": o.rfc}
            for o in (
                IF_MIB.ifDescr,
                IF_MIB.ifName,
                IF_MIB.ifAlias,
                IF_MIB.ifHighSpeed,
                IF_MIB.ifOperStatus,
                IF_MIB.ifHCInOctets,
                IF_MIB.ifHCOutOctets,
            )
        ],
    }


@router.get("", response_model=SnmpSettingsOut)
def get_snmp_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = snmp_settings.get_or_create(db)
    out = snmp_settings.to_out(row)
    return out.model_copy(update={"notes": out.notes or _default_notes()})


@router.patch("", response_model=SnmpSettingsOut)
def update_snmp_settings(
    payload: SnmpSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    row = snmp_settings.update_settings(db, payload)
    return snmp_settings.to_out(row)


@router.post("/test", response_model=SnmpTestResponse)
def test_snmp_settings(
    payload: SnmpTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    device: Device | None = None
    if payload.device_id:
        device = db.get(Device, payload.device_id)
        if not device:
            raise HTTPException(status_code=404, detail="device not found")
    elif payload.mgmt_ip:
        device = Device(
            name="snmp-test",
            vendor=Vendor.H3C,
            role=DeviceRole.LEAF,
            overlay_tech=OverlayTech.VXLAN_EVPN,
            status=DeviceStatus.UNKNOWN,
            mgmt_ip=payload.mgmt_ip,
            password=payload.community,
        )
    else:
        raise HTTPException(status_code=400, detail="device_id or mgmt_ip required")

    cfg = snmp_settings.get_or_create(db)
    if settings.dry_run:
        sample = snmp.preview_discovery(device)
        return SnmpTestResponse(
            ok=True,
            target=device.mgmt_ip,
            version=cfg.version,
            interfaces_found=len(sample),
            sample_interfaces=[i["name"] for i in sample[:8]],
            latency_ms=1.2,
            detail="dry-run 模式：返回模拟接口列表，未向设备发包",
        )

    t0 = time.perf_counter()
    try:
        found = snmp.probe_interfaces(db, device, community_override=payload.community)
    except Exception as exc:
        return SnmpTestResponse(
            ok=False,
            target=device.mgmt_ip,
            version=cfg.version,
            detail=str(exc),
        )
    latency = round((time.perf_counter() - t0) * 1000, 2)
    return SnmpTestResponse(
        ok=True,
        target=device.mgmt_ip,
        version=cfg.version,
        interfaces_found=len(found),
        sample_interfaces=[i["name"] for i in found[:8]],
        latency_ms=latency,
        detail="SNMP 探测成功",
    )


def _default_notes() -> str:
    return (
        "全局 SNMP 参数用于设备「SNMP 发现」与检测时的 IF-MIB 采集。"
        "若设备密码字段已填写 community，且开启「优先使用设备凭证」，将覆盖全局只读 community。"
    )
