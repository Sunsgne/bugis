"""Backbone link bandwidth: sync capacity from port descriptions and monitor load."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.device import Device, DeviceInterface
from app.models.link import Link
from app.services.bw_parser import format_bw_tag, parse_bw_mbps
from app.services import port_inventory, snmp_telemetry, telemetry_service

logger = logging.getLogger(__name__)

_VLAN_IFACE_RE = re.compile(
    r"^(?:Vlan-interface|Vlanif|VlanIF|Vlan)(\d+)$",
    re.IGNORECASE,
)
_TRAFFIC_SOURCES = frozenset({
    "snmp-link",
    "simulated",
    "snmp",
    "traffic_only",
    "manual",
})


def _vlan_iface_aliases(ifname: str) -> list[str]:
    """H3C Vlan-interface and Huawei Vlanif share the same VLAN id."""
    stripped = (ifname or "").strip()
    match = _VLAN_IFACE_RE.match(stripped)
    if not match:
        return [stripped] if stripped else []
    vid = match.group(1)
    return list(dict.fromkeys([
        stripped,
        f"Vlan-interface{vid}",
        f"Vlanif{vid}",
        f"VlanIF{vid}",
        f"Vlan{vid}",
    ]))


def _iface_lookup_names(db: Session, device_id: int, ifname: str) -> list[str]:
    """All interface names that may refer to the same logical port."""
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        key = (name or "").strip()
        if key and key not in seen:
            seen.add(key)
            names.append(key)

    device = db.get(Device, device_id)
    for candidate in _vlan_iface_aliases(ifname):
        add(candidate)
        if device is not None:
            try:
                add(port_inventory.resolve_interface_name(db, device, candidate))
            except Exception:
                pass
    return names


def find_interface(
    db: Session, device_id: int, interface_name: str
) -> DeviceInterface | None:
    return find_interface_for_link(db, device_id, interface_name)


def find_interface_for_link(
    db: Session, device_id: int, interface_name: str
) -> DeviceInterface | None:
    """Resolve alias/canonical names and prefer rows with SNMP ifIndex."""
    candidates: list[DeviceInterface] = []
    seen_ids: set[int] = set()
    for name in _iface_lookup_names(db, device_id, interface_name):
        row = db.execute(
            select(DeviceInterface).where(
                DeviceInterface.device_id == device_id,
                DeviceInterface.name == name,
            )
        ).scalar_one_or_none()
        if row and row.id not in seen_ids:
            seen_ids.add(row.id)
            candidates.append(row)
    if not candidates:
        return None
    with_index = [row for row in candidates if row.ifindex is not None]
    if with_index:
        return with_index[0]
    return candidates[0]


def capacity_from_interface(iface: DeviceInterface | None) -> int | None:
    if not iface:
        return None
    parsed = parse_bw_mbps(iface.description)
    if parsed:
        return parsed
    return iface.speed_mbps


def sync_link_capacity(db: Session, link: Link) -> bool:
    """Update link.capacity_mbps from endpoint port descriptions (bw tag)."""
    caps: list[int] = []
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        bw = capacity_from_interface(find_interface_for_link(db, device_id, ifname))
        if bw:
            caps.append(bw)
    if not caps:
        return False
    new_cap = min(caps)
    if link.capacity_mbps != new_cap:
        link.capacity_mbps = new_cap
        return True
    return False


def sync_all_link_capacity(db: Session) -> dict:
    links = db.execute(select(Link)).scalars().all()
    updated = 0
    for link in links:
        if sync_link_capacity(db, link):
            updated += 1
    return {"links": len(links), "updated": updated}


def enrich_interface_descriptions(db: Session, device: Device) -> int:
    """Stamp bw(...) on ports that match configured backbone links (dry-run lab only)."""
    if not settings.dry_run:
        return 0
    links = db.execute(
        select(Link).where(
            (Link.device_a_id == device.id) | (Link.device_z_id == device.id)
        )
    ).scalars().all()
    touched = 0
    for link in links:
        ifname = link.interface_a if link.device_a_id == device.id else link.interface_z
        if not ifname:
            continue
        iface = find_interface_for_link(db, device.id, ifname)
        if iface is None:
            iface = DeviceInterface(device_id=device.id, name=ifname)
            db.add(iface)
        if parse_bw_mbps(iface.description):
            continue
        bw = iface.speed_mbps or link.capacity_mbps
        iface.description = f"backbone {link.name} {format_bw_tag(bw)}"
        iface.discovered_via = iface.discovered_via or "link-sync"
        touched += 1
    db.flush()
    return touched


@dataclass
class LinkHealth:
    link_id: int
    link_name: str
    capacity_mbps: int
    traffic_mbps: float
    peak_utilization_pct: float
    avg_utilization_pct: float
    samples: int
    peak_rx_mbps: float = 0.0
    peak_tx_mbps: float = 0.0
    peak_traffic_mbps: float = 0.0
    peak_at: str | None = None


def _recent_interface_samples(
    db: Session, device_id: int, interface_name: str, limit: int = 20
):
    from app.models.telemetry import TelemetrySample

    names = _iface_lookup_names(db, device_id, interface_name)
    if not names:
        return []
    return db.execute(
        select(TelemetrySample)
        .where(
            TelemetrySample.device_id == device_id,
            or_(*[TelemetrySample.interface_name == name for name in names]),
        )
        .order_by(TelemetrySample.id.desc())
        .limit(limit)
    ).scalars().all()


def _sample_utilization_pct(sample, capacity_mbps: int) -> float:
    """Recompute utilization from live counters and current contract bandwidth."""
    cap = max(capacity_mbps, 1)
    peak_mbps = max(sample.rx_mbps or 0.0, sample.tx_mbps or 0.0)
    return round(peak_mbps / cap * 100, 2)


def compute_link_health(db: Session, link: Link, limit: int = 20) -> LinkHealth:
    cap = max(link.capacity_mbps, 1)
    utils: list[float] = []
    traffic = 0.0
    peak_sample = None
    peak_util = -1.0
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        for s in _recent_interface_samples(db, device_id, ifname, limit):
            if s.source not in _TRAFFIC_SOURCES:
                continue
            util = _sample_utilization_pct(s, cap)
            utils.append(util)
            traffic = max(traffic, (s.rx_mbps or 0.0) + (s.tx_mbps or 0.0))
            if util >= peak_util:
                peak_util = util
                peak_sample = s
    if not utils:
        return LinkHealth(
            link_id=link.id,
            link_name=link.name,
            capacity_mbps=cap,
            traffic_mbps=0.0,
            peak_utilization_pct=0.0,
            avg_utilization_pct=0.0,
            samples=0,
        )
    peak = max(utils)
    avg = sum(utils) / len(utils)
    peak_rx = peak_sample.rx_mbps if peak_sample else 0.0
    peak_tx = peak_sample.tx_mbps if peak_sample else 0.0
    peak_traffic = round(peak_rx + peak_tx, 2) if peak_sample else 0.0
    peak_at = peak_sample.created_at.isoformat() if peak_sample and peak_sample.created_at else None
    return LinkHealth(
        link_id=link.id,
        link_name=link.name,
        capacity_mbps=cap,
        traffic_mbps=round(traffic, 2),
        peak_utilization_pct=round(peak, 2),
        avg_utilization_pct=round(avg, 2),
        samples=len(utils),
        peak_rx_mbps=round(peak_rx, 2),
        peak_tx_mbps=round(peak_tx, 2),
        peak_traffic_mbps=peak_traffic,
        peak_at=peak_at,
    )


def poll_link_sample(
    db: Session,
    link: Link,
    *,
    interval_sec: float = 30.0,
) -> int:
    """Poll SNMP counters on both link endpoints; returns number of samples written."""
    if snmp_telemetry.simulation_allowed() and settings.dry_run:
        return _simulate_link_sample(db, link)

    written = 0
    cap = max(link.capacity_mbps, 1)
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        device = db.get(Device, device_id)
        iface = find_interface_for_link(db, device_id, ifname)
        if not device or not iface:
            continue
        polled = snmp_telemetry.poll_iface_counters(db, device, iface, interval_sec)
        if polled is None:
            continue
        rx, tx, errors, oper_up = polled
        peak = max(rx, tx)
        util = round(peak / cap * 100, 2)
        telemetry_service.record_sample(
            db,
            device_id=device_id,
            interface_name=iface.name,
            rx_mbps=rx,
            tx_mbps=tx,
            utilization_pct=util,
            errors=errors,
            tunnel_state="up" if oper_up else "down",
            source="snmp-link",
        )
        written += 1
    return written


def _simulate_link_sample(db: Session, link: Link) -> int:
    """Lab-only link traffic simulation."""
    import random

    cap = max(link.capacity_mbps, 1)
    util = random.uniform(15, 92)
    half = cap * util / 200.0
    written = 0
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        iface = find_interface_for_link(db, device_id, ifname)
        sample_name = iface.name if iface else ifname
        telemetry_service.record_sample(
            db,
            device_id=device_id,
            interface_name=sample_name,
            rx_mbps=round(half * random.uniform(0.8, 1.2), 2),
            tx_mbps=round(half * random.uniform(0.8, 1.2), 2),
            utilization_pct=round(util, 2),
            tunnel_state="up",
            source="simulated",
        )
        written += 1
    return written


def sample_all_links(db: Session | None = None, *, interval_sec: float = 30.0) -> int:
    """Poll SNMP counters on all links.

    Uses a fresh DB session per link so slow SNMP I/O does not hold one
    connection in an open transaction for the entire backbone sweep.
    """
    del db  # legacy arg — callers may still pass a session from scheduler
    list_db = SessionLocal()
    try:
        link_ids = list(list_db.execute(select(Link.id)).scalars().all())
    finally:
        list_db.close()

    total = 0
    for link_id in link_ids:
        link_db = SessionLocal()
        try:
            link = link_db.get(Link, link_id)
            if not link:
                continue
            total += poll_link_sample(link_db, link, interval_sec=interval_sec)
            link_db.commit()
        except Exception as exc:  # noqa: BLE001 — one bad link must not stall the sweep
            link_db.rollback()
            logger.warning("link SNMP sample failed for link_id=%s: %s", link_id, exc)
        finally:
            link_db.close()
    return total


def evaluate_all_links(db: Session) -> None:
    from app.services import alarm_service

    links = db.execute(select(Link)).scalars().all()
    for link in links:
        health = compute_link_health(db, link)
        alarm_service.evaluate_link_health(db, link, health)
