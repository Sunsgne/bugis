"""SNMP interface discovery.

Discovers a device's interfaces so they become selectable when provisioning
circuits. Walks IF-MIB (ifDescr/ifAlias/ifHighSpeed/ifOperStatus) via pysnmp
when SNMP is enabled. Dry-run only affects config push — not read-only SNMP.
If a live walk fails while dry-run is on, falls back to vendor-shaped simulation
for demo / CI; otherwise the error is raised to the caller.

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
from app.models.snmp_settings import SnmpSettings
from app.services import snmp_device
from app.services import snmp_settings as snmp_cfg
from app.services.mib_registry import IF_MIB, IF_OPER_STATUS

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

OPER_MAP = IF_OPER_STATUS


def preview_discovery(device: Device) -> list[dict]:
    """Return synthesized interfaces without persisting (for SNMP test in dry-run)."""
    return _synthesize(device)


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


def _auth_proto(name: str | None):
    from pysnmp.hlapi import (  # pragma: no cover
        usmAesCfb128Protocol,
        usmAesCfb192Protocol,
        usmAesCfb256Protocol,
        usmDESPrivProtocol,
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
    )

    mapping = {
        "MD5": usmHMACMD5AuthProtocol,
        "SHA": usmHMACSHAAuthProtocol,
        "DES": usmDESPrivProtocol,
        "AES": usmAesCfb128Protocol,
        "AES128": usmAesCfb128Protocol,
        "AES192": usmAesCfb192Protocol,
        "AES256": usmAesCfb256Protocol,
    }
    return mapping.get((name or "").upper())


def _build_credentials(device: Device, cfg: SnmpSettings, community: str):
    from pysnmp.hlapi import CommunityData, UsmUserData  # pragma: no cover

    eff = snmp_device.effective_snmp(device, cfg)
    version = eff["version"]
    if version == "3":
        level = eff["v3_security_level"] or "authPriv"
        auth_key = eff["v3_auth_password"] if level != "noAuthNoPriv" else None
        priv_key = eff["v3_priv_password"] if level == "authPriv" else None
        return UsmUserData(
            eff["v3_username"] or "",
            authKey=auth_key,
            privKey=priv_key,
            authProtocol=_auth_proto(eff["v3_auth_protocol"]),
            privProtocol=_auth_proto(eff["v3_priv_protocol"]),
        )
    return CommunityData(community, mpModel=1 if version == "2c" else 0)


def _walk_oid(
    device: Device,
    oid: str,
    cfg: SnmpSettings,
    community: str,
    *,
    port: int | None = None,
) -> dict[int, str]:
    from pysnmp.hlapi import (  # pragma: no cover
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        nextCmd,
    )

    out: dict[int, str] = {}
    eff = snmp_device.effective_snmp(device, cfg)
    creds = _build_credentials(device, cfg, community)
    ctx = (
        ContextData(eff["v3_context_name"])
        if eff["version"] == "3" and eff["v3_context_name"]
        else ContextData()
    )
    for (errInd, errStat, _idx, varBinds) in nextCmd(
        SnmpEngine(),
        creds,
        UdpTransportTarget(
            (device.mgmt_ip, port or cfg.port),
            timeout=cfg.timeout_sec,
            retries=cfg.retries,
        ),
        ctx,
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
        maxRepetitions=cfg.max_repetitions,
    ):
        if errInd or errStat:
            break
        for oid_val, val in varBinds:
            ifindex = int(str(oid_val).rsplit(".", 1)[-1])
            out[ifindex] = str(val)
    return out


def probe_interfaces(
    db: Session,
    device: Device,
    *,
    community_override: str | None = None,
) -> list[dict]:
    """Walk IF-MIB once and return raw interface dicts (no DB write)."""
    cfg = snmp_cfg.get_or_create(db)
    device_snmp = snmp_device.effective_snmp(device)
    if not cfg.enabled:
        raise RuntimeError("SNMP 采集已在平台设置中关闭")
    if not device_snmp["enabled"]:
        raise RuntimeError("该设备已关闭 SNMP 采集")
    community = snmp_cfg.effective_community(db, device, community_override)
    return _walk_real(device, cfg, community, port=device_snmp["port"])


def _walk_real(
    device: Device,
    cfg: SnmpSettings,
    community: str,
    *,
    port: int | None = None,
) -> list[dict]:  # pragma: no cover
    try:
        import pysnmp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "pysnmp not installed; install it or run in dry-run mode"
        ) from exc

    walk_port = port or cfg.port
    names_descr = (
        _walk_oid(device, IF_MIB.ifDescr.oid, cfg, community, port=walk_port)
        if cfg.walk_if_descr
        else {}
    )
    names_canonical = _walk_oid(device, IF_MIB.ifName.oid, cfg, community, port=walk_port)
    names = names_descr.copy()
    for ifindex, if_name in names_canonical.items():
        if if_name.strip():
            names[ifindex] = if_name.strip()
    if not names:
        raise RuntimeError("未采集到 ifDescr/ifName，请检查 community / 网络可达性 / SNMP 版本")

    aliases = (
        _walk_oid(device, IF_MIB.ifAlias.oid, cfg, community, port=walk_port)
        if cfg.walk_if_alias
        else {}
    )
    speeds = (
        _walk_oid(device, IF_MIB.ifHighSpeed.oid, cfg, community, port=walk_port)
        if cfg.walk_if_high_speed
        else {}
    )
    opers = (
        _walk_oid(device, IF_MIB.ifOperStatus.oid, cfg, community, port=walk_port)
        if cfg.walk_if_oper_status
        else {}
    )

    results: list[dict] = []
    for ifindex, name in names.items():
        if not snmp_cfg.interface_allowed(name, cfg):
            continue
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

    cfg = snmp_cfg.get_or_create(db)
    device_snmp = snmp_device.effective_snmp(device)
    if not cfg.enabled or not device_snmp["enabled"]:
        discovered: list[dict] = []
    else:
        community = snmp_cfg.effective_community(db, device)
        try:
            discovered = _walk_real(device, cfg, community, port=device_snmp["port"])
        except (RuntimeError, ImportError, ModuleNotFoundError):
            if settings.dry_run:
                discovered = _synthesize(device)
            else:
                raise

    existing = {
        i.name: i
        for i in db.execute(
            select(DeviceInterface).where(DeviceInterface.device_id == device.id)
        ).scalars().all()
    }

    if discovered and discovered[0].get("discovered_via") == "snmp":
        for name, iface in list(existing.items()):
            if iface.discovered_via != "snmp-sim":
                continue
            if iface.allocated or iface.used_s_vids:
                continue
            db.delete(iface)
            del existing[name]

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
    if cfg.sync_link_capacity:
        link_monitor.enrich_interface_descriptions(db, device)
        link_monitor.sync_all_link_capacity(db)
    return list(existing.values())
