"""Bandwidth capacity computation across devices, sites and links."""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device, DeviceInterface
from app.models.enums import CircuitStatus
from app.models.link import Link
from app.models.site import Site
from app.services.link_planner import is_bridge_aggregation, is_vlan_interface
from app.services.port_inventory import is_huawei_subinterface

_SYSTEM_IFACE = re.compile(
    r"loop(?:back)?|null0|inloop|console|register|meth\d|management|mgmt|vbdif",
    re.IGNORECASE,
)
_SUBIF_SUFFIX = re.compile(r"\.\d+$")


def is_physical_capacity_interface(name: str) -> bool:
    """True for fabric physical ports; excludes VLAN/SVI, sub-interfaces and system ifaces."""
    stripped = (name or "").strip()
    if not stripped or _SYSTEM_IFACE.search(stripped):
        return False
    if is_vlan_interface(stripped) or is_bridge_aggregation(stripped):
        return False
    if is_huawei_subinterface(stripped):
        return False
    if _SUBIF_SUFFIX.search(stripped) and re.search(r"\d+/\d+", stripped):
        return False
    return True


def _physical_capacity_mbps(interfaces: list[DeviceInterface]) -> int:
    return sum(
        (iface.speed_mbps or 0)
        for iface in interfaces
        if is_physical_capacity_interface(iface.name)
    )


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
    devices = db.execute(
        select(Device).options(selectinload(Device.interfaces))
    ).scalars().all()
    result = []
    for d in devices:
        # Fabric capacity counts physical port speeds only (no VLAN/SVI/sub-if).
        total = _physical_capacity_mbps(d.interfaces) or 40000
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


def _link_capacity_rows(
    db: Session,
    links: list[Link],
    health_by_id: dict,
) -> list[dict]:
    from app.services import igp_cost_service, link_alarm_settings, link_monitor, link_planner, platform_settings

    plat = platform_settings.get_or_create(db)
    site_by_id = {s.id: s for s in db.execute(select(Site)).scalars().all()}
    device_ids = {l.device_a_id for l in links} | {l.device_z_id for l in links}
    backbone_cache = igp_cost_service.build_backbone_cache(db, device_ids)
    result = []
    for l in links:
        da = db.get(Device, l.device_a_id)
        dz = db.get(Device, l.device_z_id)
        site_a = site_by_id.get(da.site_id) if da and da.site_id else None
        site_z = site_by_id.get(dz.site_id) if dz and dz.site_id else None
        health = health_by_id.get(l.id) or link_monitor.compute_link_health(db, l)
        alarm = link_alarm_settings.thresholds_out(l, plat)
        igp = igp_cost_service.link_backbone_igp(db, l, backbone_cache=backbone_cache)
        result.append({
            "link_id": l.id,
            "name": l.name,
            "type": l.type.value,
            "supplier": l.supplier,
            "device_a_id": l.device_a_id,
            "device_z_id": l.device_z_id,
            "device_a": da.name if da else l.device_a_id,
            "device_z": dz.name if dz else l.device_z_id,
            "site_a_id": site_a.id if site_a else None,
            "site_z_id": site_z.id if site_z else None,
            "site_a": site_a.name if site_a else None,
            "site_z": site_z.name if site_z else None,
            "site_a_code": site_a.code if site_a else None,
            "site_z_code": site_z.code if site_z else None,
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
            "peak_rx_mbps": health.peak_rx_mbps,
            "peak_tx_mbps": health.peak_tx_mbps,
            "peak_traffic_mbps": health.peak_traffic_mbps,
            "peak_at": health.peak_at,
            "utilization_pct": health.peak_utilization_pct,
            "samples": health.samples,
            **igp,
        })
    return result


def link_capacity(db: Session) -> list[dict]:
    from app.services import link_monitor

    links = db.execute(select(Link)).scalars().all()
    health_by_id = link_monitor.batch_compute_link_health(db, links)
    return _link_capacity_rows(db, links, health_by_id)


def topology(
    db: Session,
    *,
    health_by_id: dict | None = None,
) -> dict:
    """Nodes (devices grouped by site) and edges (links) for visualization."""
    from app.services import link_monitor

    sites = db.execute(select(Site)).scalars().all()
    devices = db.execute(select(Device)).scalars().all()
    links = db.execute(select(Link)).scalars().all()
    if health_by_id is None:
        health_by_id = link_monitor.batch_compute_link_health(db, links)
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
                "utilization_pct": (
                    health_by_id[l.id].peak_utilization_pct
                    if l.id in health_by_id
                    else 0.0
                ),
            }
            for l in links
        ],
    }


def capacity_overview(db: Session) -> dict:
    """Single round-trip payload for the capacity planning page."""
    from app.models.enums import CircuitStatus
    from app.services import link_monitor

    links = db.execute(select(Link)).scalars().all()
    health_by_id = link_monitor.batch_compute_link_health(db, links)
    return {
        "sites": site_capacity(db),
        "links": _link_capacity_rows(db, links, health_by_id),
        "topology": topology(db, health_by_id=health_by_id),
        "total_active_bandwidth_mbps": int(
            db.scalar(
                select(func.coalesce(func.sum(Circuit.bandwidth_mbps), 0)).where(
                    Circuit.status == CircuitStatus.ACTIVE
                )
            )
            or 0
        ),
    }


def get_topology_layout(db: Session) -> dict[str, dict[str, float]]:
    from app.services import platform_settings

    plat = platform_settings.get_or_create(db)
    raw = plat.topology_layout if isinstance(plat.topology_layout, dict) else {}
    out: dict[str, dict[str, float]] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        try:
            x = float(val.get("x", 0))
            y = float(val.get("y", 0))
        except (TypeError, ValueError):
            continue
        out[str(key)] = {"x": x, "y": y}
    return out


def save_topology_layout(db: Session, positions: dict) -> dict[str, dict[str, float]]:
    from app.services import platform_settings

    if not isinstance(positions, dict):
        raise ValueError("positions must be an object")

    device_ids = {str(i) for i in db.execute(select(Device.id)).scalars().all()}
    cleaned: dict[str, dict[str, float]] = {}
    for key, val in positions.items():
        sk = str(key)
        if sk not in device_ids or not isinstance(val, dict):
            continue
        try:
            x = float(val.get("x", 0))
            y = float(val.get("y", 0))
        except (TypeError, ValueError):
            continue
        cleaned[sk] = {"x": x, "y": y}

    plat = platform_settings.get_or_create(db)
    plat.topology_layout = cleaned or None
    db.commit()
    return get_topology_layout(db)
