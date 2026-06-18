"""Bandwidth capacity computation across devices, sites and links."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import CircuitStatus
from app.models.link import Link
from app.models.site import Site


def _active_circuit_load_by_device(db: Session) -> dict[int, int]:
    """Sum of active circuit bandwidth attached to each device (via endpoints)."""
    rows = db.execute(
        select(CircuitEndpoint.device_id, Circuit.bandwidth_mbps)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(Circuit.status == CircuitStatus.ACTIVE)
    ).all()
    load: dict[int, int] = {}
    for device_id, bw in rows:
        load[device_id] = load.get(device_id, 0) + (bw or 0)
    return load


def device_capacity(db: Session) -> list[dict]:
    load = _active_circuit_load_by_device(db)
    devices = db.execute(select(Device)).scalars().all()
    result = []
    for d in devices:
        # Total device capacity approximated from sum of interface speeds.
        total = sum((i.speed_mbps or 0) for i in d.interfaces) or 40000
        used = load.get(d.id, 0)
        result.append({
            "device_id": d.id,
            "device": d.name,
            "vendor": d.vendor.value,
            "site_id": d.site_id,
            "capacity_mbps": total,
            "used_mbps": used,
            "utilization_pct": round(used / total * 100, 1) if total else 0.0,
        })
    return result


def site_capacity(db: Session) -> list[dict]:
    dev_cap = {d["device_id"]: d for d in device_capacity(db)}
    sites = db.execute(select(Site)).scalars().all()
    result = []
    for s in sites:
        members = [c for c in dev_cap.values() if c["site_id"] == s.id]
        total = sum(c["capacity_mbps"] for c in members)
        used = sum(c["used_mbps"] for c in members)
        result.append({
            "site_id": s.id,
            "site": s.name,
            "code": s.code,
            "devices": len(members),
            "capacity_mbps": total,
            "used_mbps": used,
            "utilization_pct": round(used / total * 100, 1) if total else 0.0,
        })
    return result


def link_capacity(db: Session) -> list[dict]:
    from app.services import link_alarm_settings, link_monitor, link_planner, platform_settings

    plat = platform_settings.get_or_create(db)
    links = db.execute(select(Link)).scalars().all()
    result = []
    for l in links:
        da = db.get(Device, l.device_a_id)
        dz = db.get(Device, l.device_z_id)
        health = link_monitor.compute_link_health(db, l)
        alarm = link_alarm_settings.thresholds_out(l, plat)
        result.append({
            "link_id": l.id,
            "name": l.name,
            "type": l.type.value,
            "device_a_id": l.device_a_id,
            "device_z_id": l.device_z_id,
            "device_a": da.name if da else l.device_a_id,
            "device_z": dz.name if dz else l.device_z_id,
            "interface_a": l.interface_a,
            "interface_z": l.interface_z,
            "interface_a_description": link_planner._interface_description(
                db, l.device_a_id, l.interface_a or ""
            ),
            "interface_z_description": link_planner._interface_description(
                db, l.device_z_id, l.interface_z or ""
            ),
            "capacity_mbps": l.capacity_mbps,
            "reserved_mbps": l.reserved_mbps,
            "alarm_utilization_pct": l.alarm_utilization_pct,
            **alarm,
            "traffic_mbps": health.traffic_mbps,
            "peak_utilization_pct": health.peak_utilization_pct,
            "avg_utilization_pct": health.avg_utilization_pct,
            "utilization_pct": health.peak_utilization_pct,
            "samples": health.samples,
        })
    return result


def topology(db: Session) -> dict:
    """Nodes (devices grouped by site) and edges (links) for visualization."""
    from app.services import link_monitor

    sites = db.execute(select(Site)).scalars().all()
    devices = db.execute(select(Device)).scalars().all()
    links = db.execute(select(Link)).scalars().all()
    return {
        "sites": [{"id": s.id, "name": s.name, "code": s.code} for s in sites],
        "nodes": [
            {
                "id": d.id,
                "name": d.name,
                "vendor": d.vendor.value,
                "role": d.role.value,
                "overlay_tech": d.overlay_tech.value,
                "site_id": d.site_id,
                "status": d.status.value,
            }
            for d in devices
        ],
        "edges": [
            {
                "id": l.id,
                "name": l.name,
                "type": l.type.value,
                "source": l.device_a_id,
                "target": l.device_z_id,
                "capacity_mbps": l.capacity_mbps,
                "reserved_mbps": l.reserved_mbps,
                "utilization_pct": link_monitor.compute_link_health(db, l).peak_utilization_pct,
            }
            for l in links
        ],
    }
