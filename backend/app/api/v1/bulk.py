"""Bulk CSV import / export for devices and circuits."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import (
    DeviceRole,
    DeviceStatus,
    OverlayTech,
    Vendor,
)
from app.models.site import Site
from app.models.tenant import Tenant
from app.models.user import User
from app.services import config_learn
from app.services import platform_settings as platform_cfg

router = APIRouter()

DEVICE_COLUMNS = [
    "name", "vendor", "model", "role", "overlay_tech", "status",
    "mgmt_ip", "loopback_ip", "bgp_asn", "sr_node_sid", "site_code",
]


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/devices/export")
def export_devices(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    devices = db.execute(select(Device).order_by(Device.id)).scalars().all()
    sites = {s.id: s.code for s in db.execute(select(Site)).scalars().all()}
    rows = [
        {
            "name": d.name,
            "vendor": d.vendor.value,
            "model": d.model or "",
            "role": d.role.value,
            "overlay_tech": d.overlay_tech.value,
            "status": d.status.value,
            "mgmt_ip": d.mgmt_ip,
            "loopback_ip": d.loopback_ip or "",
            "bgp_asn": d.bgp_asn or "",
            "sr_node_sid": d.sr_node_sid or "",
            "site_code": sites.get(d.site_id, ""),
        }
        for d in devices
    ]
    return _csv_response(rows, DEVICE_COLUMNS, "devices.csv")


@router.post("/devices/import")
def import_devices(
    file: UploadFile = File(...),
    learn: bool | None = Query(default=None, description="导入后对新增设备执行现网配置学习；省略则跟随平台设置"),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    try:
        text = file.file.read().decode("utf-8-sig")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"cannot read file: {exc}")

    plat = platform_cfg.get_or_create(db)
    do_learn = plat.auto_learn_on_import if learn is None else learn

    reader = csv.DictReader(io.StringIO(text))
    sites = {s.code: s.id for s in db.execute(select(Site)).scalars().all()}
    existing = {
        d.name for d in db.execute(select(Device.name)).all()  # type: ignore
    }
    created, skipped, errors = 0, 0, []
    new_device_ids: list[int] = []
    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if name in existing:
            skipped += 1
            continue
        try:
            device = Device(
                name=name,
                vendor=Vendor((row.get("vendor") or "h3c").strip().lower()),
                model=(row.get("model") or "").strip() or None,
                role=DeviceRole((row.get("role") or "leaf").strip().lower()),
                overlay_tech=OverlayTech(
                    (row.get("overlay_tech") or "vxlan_evpn").strip().lower()
                ),
                status=DeviceStatus(
                    (row.get("status") or "unknown").strip().lower()
                ),
                mgmt_ip=(row.get("mgmt_ip") or "").strip() or "0.0.0.0",
                loopback_ip=(row.get("loopback_ip") or "").strip() or None,
                bgp_asn=int(row["bgp_asn"]) if row.get("bgp_asn") else None,
                sr_node_sid=int(row["sr_node_sid"]) if row.get("sr_node_sid") else None,
                site_id=sites.get((row.get("site_code") or "").strip()),
            )
            db.add(device)
            db.flush()
            new_device_ids.append(device.id)
            existing.add(name)
            created += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"row {i}: {exc}")

    learn_summary = None
    if do_learn and new_device_ids:
        learn_summary = config_learn.learn_devices_batch(
            db, new_device_ids, created_by=user.username
        )

    db.commit()
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "learn_enabled": do_learn,
        "learn": learn_summary,
    }


@router.get("/circuits/export")
def export_circuits(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Circuit).order_by(Circuit.id)
    if tenant_id:
        stmt = stmt.where(Circuit.tenant_id == tenant_id)
    circuits = db.execute(stmt).scalars().all()
    tenants = {t.id: t.code for t in db.execute(select(Tenant)).scalars().all()}
    devices = {d.id: d.name for d in db.execute(select(Device)).scalars().all()}
    columns = [
        "code", "name", "tenant_code", "service_type", "status", "vni", "vsi_name", "vlan_id",
        "vrf_name", "rd", "rt", "bandwidth_mbps", "sla_target", "endpoints",
    ]
    rows = []
    for c in circuits:
        eps = ";".join(
            f"{e.label}:{devices.get(e.device_id, e.device_id)}:{e.interface_name}"
            for e in c.endpoints
        )
        rows.append({
            "code": c.code,
            "name": c.name,
            "tenant_code": tenants.get(c.tenant_id, ""),
            "service_type": c.service_type.value,
            "status": c.status.value,
            "vni": c.vni or "",
            "vsi_name": c.vsi_name or "",
            "vlan_id": c.vlan_id or "",
            "vrf_name": c.vrf_name or "",
            "rd": c.route_distinguisher or "",
            "rt": c.route_target or "",
            "bandwidth_mbps": c.bandwidth_mbps,
            "sla_target": c.sla_target or "",
            "endpoints": eps,
        })
    return _csv_response(rows, columns, "circuits.csv")
