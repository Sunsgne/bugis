"""SNMP interface discovery.

Discovers a device's interfaces so they become selectable when provisioning
circuits. In dry-run mode it synthesizes a vendor-appropriate interface set;
in live mode it walks IF-MIB (ifDescr/ifAlias/ifHighSpeed/ifOperStatus) via
pysnmp (optional dependency).

Port descriptions may contain contracted bandwidth tags like ``bw(100Mbps)``;
these are stored on ``DeviceInterface.description`` and synced to backbone
``Link.capacity_mbps`` after discovery.
"""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceInterface
from app.models.enums import Vendor

# Vendor interface naming conventions: (access_pattern, count, uplink_pattern, uplink_count, speed)
VENDOR_INTERFACES: dict[Vendor, list[tuple[str, int, int]]] = {
    # (pattern with {i}, count, speed_mbps)
    Vendor.H3C: [("GigabitEthernet1/0/{i}", 24, 1000),
                 ("Ten-GigabitEthernet1/0/{i}", 4, 10000),
                 ("HundredGigE1/0/{i}", 2, 100000)],
    Vendor.HUAWEI: [("GE1/0/{i}", 24, 1000), ("10GE1/0/{i}", 4, 10000),
                    ("HundredGE1/0/{i}", 2, 100000)],
    Vendor.CISCO: [("GigabitEthernet0/0/0/{i}", 12, 1000),
                   ("TenGigE0/0/0/{i}", 4, 10000),
                   ("HundredGigE0/0/0/{i}", 2, 100000)],
    Vendor.JUNIPER: [("ge-0/0/{i}", 12, 1000), ("xe-0/0/{i}", 4, 10000),
                     ("et-0/0/{i}", 2, 100000)],
    Vendor.ARISTA: [("Ethernet{i}", 32, 10000)],
    Vendor.FRR: [("swp{i}", 32, 25000)],
}

OPER_MAP = {1: "up", 2: "down", 3: "testing", 4: "unknown", 5: "dormant", 6: "notPresent", 7: "lowerLayerDown"}


def _synthesize(device: Device) -> list[dict]:
    specs = VENDOR_INTERFACES.get(device.vendor, [("Ethernet{i}", 8, 1000)])
    ifaces: list[dict] = []
    ifindex = 1
    for pattern, count, speed in specs:
        start = 0 if "{i}" in pattern and device.vendor in (
            Vendor.ARISTA,) else 1
        for n in range(count):
            idx = start + n
            ifaces.append({
                "name": pattern.format(i=idx),
                "speed_mbps": speed,
                "oper_status": "up" if random.random() > 0.25 else "down",
                "ifindex": ifindex,
                "discovered_via": "snmp-sim",
                "description": None,
            })
            ifindex += 1
    return ifaces


def _walk_oid(device: Device, oid: str) -> dict[int, str]:
    from pysnmp.hlapi import (  # pragma: no cover
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        nextCmd,
    )

    community = device.password or "public"
    out: dict[int, str] = {}
    for (errInd, errStat, _idx, varBinds) in nextCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((device.mgmt_ip, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if errInd or errStat:
            break
        for oid_val, val in varBinds:
            ifindex = int(str(oid_val).rsplit(".", 1)[-1])
            out[ifindex] = str(val)
    return out


def _walk_real(device: Device) -> list[dict]:  # pragma: no cover - needs device
    try:
        import pysnmp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "pysnmp not installed; install it or run in dry-run mode"
        ) from exc

    names = _walk_oid(device, "1.3.6.1.2.1.2.2.1.2")  # ifDescr
    aliases = _walk_oid(device, "1.3.6.1.2.1.31.1.1.1.18")  # ifAlias
    speeds = _walk_oid(device, "1.3.6.1.2.1.31.1.1.1.15")  # ifHighSpeed (Mbps)
    opers = _walk_oid(device, "1.3.6.1.2.1.2.2.1.8")  # ifOperStatus

    results: list[dict] = []
    for ifindex, name in names.items():
        alias = aliases.get(ifindex, "")
        description = alias.strip() or None
        speed_raw = speeds.get(ifindex)
        speed_mbps = int(speed_raw) if speed_raw and speed_raw.isdigit() else None
        oper_raw = opers.get(ifindex)
        oper_status = OPER_MAP.get(int(oper_raw), "unknown") if oper_raw and oper_raw.isdigit() else "unknown"
        results.append({
            "name": name,
            "description": description,
            "speed_mbps": speed_mbps,
            "oper_status": oper_status,
            "ifindex": ifindex,
            "discovered_via": "snmp",
        })
    return results


def discover_interfaces(db: Session, device: Device) -> list[DeviceInterface]:
    """Discover and upsert a device's interfaces. Returns the current set."""
    from app.services import link_monitor

    discovered = _synthesize(device) if settings.dry_run else _walk_real(device)

    existing = {
        i.name: i
        for i in db.execute(
            select(DeviceInterface).where(DeviceInterface.device_id == device.id)
        ).scalars().all()
    }
    for d in discovered:
        iface = existing.get(d["name"])
        if iface is None:
            iface = DeviceInterface(device_id=device.id, name=d["name"])
            db.add(iface)
            existing[d["name"]] = iface
        if d.get("description") is not None:
            iface.description = d["description"]
        iface.speed_mbps = d.get("speed_mbps")
        iface.oper_status = d.get("oper_status")
        iface.ifindex = d.get("ifindex")
        iface.discovered_via = d.get("discovered_via")

    db.flush()
    link_monitor.enrich_interface_descriptions(db, device)
    link_monitor.sync_all_link_capacity(db)
    return list(existing.values())
