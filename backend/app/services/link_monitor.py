"""Backbone link bandwidth: sync capacity from port descriptions and monitor load."""
from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceInterface
from app.models.link import Link
from app.services.bw_parser import format_bw_tag, parse_bw_mbps
from app.services import telemetry_service


def find_interface(
    db: Session, device_id: int, interface_name: str
) -> DeviceInterface | None:
    return db.execute(
        select(DeviceInterface).where(
            DeviceInterface.device_id == device_id,
            DeviceInterface.name == interface_name,
        )
    ).scalar_one_or_none()


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
        bw = capacity_from_interface(find_interface(db, device_id, ifname))
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
    """In dry-run, stamp bw(...) on ports that match configured backbone links."""
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
        iface = find_interface(db, device.id, ifname)
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


def _recent_interface_samples(
    db: Session, device_id: int, interface_name: str, limit: int = 20
):
    from app.models.telemetry import TelemetrySample

    return db.execute(
        select(TelemetrySample)
        .where(
            TelemetrySample.device_id == device_id,
            TelemetrySample.interface_name == interface_name,
        )
        .order_by(TelemetrySample.id.desc())
        .limit(limit)
    ).scalars().all()


def compute_link_health(db: Session, link: Link, limit: int = 20) -> LinkHealth:
    utils: list[float] = []
    traffic = 0.0
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        for s in _recent_interface_samples(db, device_id, ifname, limit):
            utils.append(s.utilization_pct)
            traffic = max(traffic, s.rx_mbps + s.tx_mbps)
    cap = max(link.capacity_mbps, 1)
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
    return LinkHealth(
        link_id=link.id,
        link_name=link.name,
        capacity_mbps=cap,
        traffic_mbps=round(traffic, 2),
        peak_utilization_pct=round(peak, 2),
        avg_utilization_pct=round(avg, 2),
        samples=len(utils),
    )


def simulate_link_sample(db: Session, link: Link) -> None:
    """Generate traffic samples on both link endpoints (dry-run / lab)."""
    cap = max(link.capacity_mbps, 1)
    # Skew high occasionally so link utilization alarms are visible in demo.
    util = random.uniform(15, 92)
    half = cap * util / 200.0
    for device_id, ifname in (
        (link.device_a_id, link.interface_a),
        (link.device_z_id, link.interface_z),
    ):
        if not ifname:
            continue
        telemetry_service.record_sample(
            db,
            device_id=device_id,
            interface_name=ifname,
            rx_mbps=round(half * random.uniform(0.8, 1.2), 2),
            tx_mbps=round(half * random.uniform(0.8, 1.2), 2),
            utilization_pct=round(util, 2),
            latency_ms=round(random.uniform(0.5, 3.0), 2),
            jitter_ms=round(random.uniform(0.05, 0.5), 2),
            packet_loss_pct=round(random.uniform(0, 0.05), 3),
            tunnel_state="up",
        )


def sample_all_links(db: Session) -> int:
    links = db.execute(select(Link)).scalars().all()
    for link in links:
        simulate_link_sample(db, link)
    return len(links)


def evaluate_all_links(db: Session) -> None:
    from app.services import alarm_service

    links = db.execute(select(Link)).scalars().all()
    for link in links:
        health = compute_link_health(db, link)
        alarm_service.evaluate_link_health(db, link, health)
