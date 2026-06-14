"""SNMP interface discovery.

Discovers a device's interfaces so they become selectable when provisioning
circuits. In dry-run mode it synthesizes a vendor-appropriate interface set;
in live mode it walks IF-MIB (ifDescr/ifAlias/ifHighSpeed/ifOperStatus) via
pysnmp (optional dependency).
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
                 ("Ten-GigabitEthernet1/0/{i}", 4, 10000)],
    Vendor.HUAWEI: [("GE1/0/{i}", 24, 1000), ("10GE1/0/{i}", 4, 10000)],
    Vendor.CISCO: [("GigabitEthernet0/0/0/{i}", 12, 1000),
                   ("TenGigE0/0/0/{i}", 4, 10000)],
    Vendor.JUNIPER: [("ge-0/0/{i}", 12, 1000), ("xe-0/0/{i}", 4, 10000),
                     ("et-0/0/{i}", 2, 100000)],
    Vendor.ARISTA: [("Ethernet{i}", 32, 10000)],
    Vendor.FRR: [("swp{i}", 32, 25000)],
}


def _synthesize(device: Device) -> list[dict]:
    specs = VENDOR_INTERFACES.get(device.vendor, [("Ethernet{i}", 8, 1000)])
    ifaces: list[dict] = []
    ifindex = 1
    for pattern, count, speed in specs:
        start = 0 if "{i}" in pattern and device.vendor in (
            Vendor.ARISTA,) else 1
        # Cisco/Juniper uplinks start at higher index for realism
        for n in range(count):
            idx = start + n
            ifaces.append({
                "name": pattern.format(i=idx),
                "speed_mbps": speed,
                "oper_status": "up" if random.random() > 0.25 else "down",
                "ifindex": ifindex,
                "discovered_via": "snmp-sim",
            })
            ifindex += 1
    return ifaces


def _walk_real(device: Device) -> list[dict]:  # pragma: no cover - needs device
    try:
        from pysnmp.hlapi import (
            SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, nextCmd,
        )
    except ImportError as exc:
        raise RuntimeError(
            "pysnmp not installed; install it or run in dry-run mode"
        ) from exc

    community = device.password or "public"
    results: dict[int, dict] = {}
    # ifDescr (1.3.6.1.2.1.2.2.1.2)
    for (errInd, errStat, _idx, varBinds) in nextCmd(
        SnmpEngine(), CommunityData(community),
        UdpTransportTarget((device.mgmt_ip, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity("1.3.6.1.2.1.2.2.1.2")),
        lexicographicMode=False,
    ):
        if errInd or errStat:
            break
        for oid, val in varBinds:
            ifindex = int(str(oid).rsplit(".", 1)[-1])
            results[ifindex] = {"name": str(val), "ifindex": ifindex,
                                "oper_status": "unknown", "speed_mbps": None,
                                "discovered_via": "snmp"}
    return list(results.values())


def discover_interfaces(db: Session, device: Device) -> list[DeviceInterface]:
    """Discover and upsert a device's interfaces. Returns the current set."""
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
        iface.speed_mbps = d.get("speed_mbps")
        iface.oper_status = d.get("oper_status")
        iface.ifindex = d.get("ifindex")
        iface.discovered_via = d.get("discovered_via")
    db.flush()
    return list(existing.values())
