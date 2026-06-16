"""Port S-VID / VLAN inventory: discover what is already in use on each interface.

Prevents provisioning collisions by combining:
  1. Platform intent (circuit endpoints on active/pending circuits)
  2. Device running-config (parsed from assembled config or live CLI in production)

Invoked during device check and SNMP interface discovery.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device, DeviceInterface
from app.models.enums import AccessMode, CircuitStatus, Vendor
from app.models.tenant import Tenant
from app.services import config_mgmt

# Circuits whose endpoints should reserve S-VID on a port.
RESERVING_STATUSES = frozenset({
    CircuitStatus.ACTIVE,
    CircuitStatus.PROVISIONING,
    CircuitStatus.PENDING,
    CircuitStatus.DEGRADED,
    CircuitStatus.DRAFT,
})

# Demo-only: legacy config fragments not tracked by the platform (dry-run realism).
_LEGACY_SIM: dict[str, list[dict]] = {
    "SH-PE-01": [
        {
            "interface": "GigabitEthernet0/0/0/2",
            "access_mode": "dot1q",
            "s_vid": 150,
            "c_vid": None,
            "note": "legacy manual AC",
        },
        {
            "interface": "GigabitEthernet0/0/0/3",
            "access_mode": "dot1q",
            "s_vid": 280,
            "c_vid": None,
            "note": "legacy manual AC",
        },
    ],
    "BJ-LEAF-01": [
        {
            "interface": "GE1/0/5",
            "access_mode": "dot1q",
            "s_vid": 120,
            "c_vid": None,
            "note": "legacy manual AC",
        },
    ],
}


@dataclass
class SvidEntry:
    s_vid: int | None
    c_vid: int | None = None
    access_mode: str = "dot1q"
    circuit_code: str | None = None
    source: str = "platform"  # platform | device | legacy
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "s_vid": self.s_vid,
            "c_vid": self.c_vid,
            "access_mode": self.access_mode,
            "circuit_code": self.circuit_code,
            "source": self.source,
            **({"note": self.note} if self.note else {}),
        }

    def key(self) -> tuple:
        return (self.access_mode, self.s_vid, self.c_vid)


@dataclass
class PortUsage:
    interface_name: str
    entries: list[SvidEntry] = field(default_factory=list)

    @property
    def allocated(self) -> bool:
        return len(self.entries) > 0


def _normalize_iface(name: str) -> str:
    return name.strip()


def _iface_port_suffix(name: str) -> str | None:
    """Extract chassis/slot/port suffix e.g. 1/0/25 from any interface name."""
    m = re.search(r"(\d+(?:/\d+)+)\s*$", name.strip())
    return m.group(1) if m else None


def _iface_aliases(name: str) -> set[str]:
    """Common H3C/Cisco SNMP vs CLI naming variants."""
    norm = _normalize_iface(name)
    aliases = {norm}
    suffix = _iface_port_suffix(norm)
    if not suffix:
        return aliases
    prefixes = (
        r"Twenty-FiveGigE",
        r"Ten-GigabitEthernet",
        r"TenGigabitEthernet",
        r"TenGigE",
        r"HundredGigE",
        r"FortyGigE",
        r"GigabitEthernet",
        r"GE",
        r"25GE",
        r"10GE",
        r"100GE",
        r"40GE",
        r"Ethernet",
        r"xe-",
        r"ge-",
        r"et-",
    )
    for prefix in prefixes:
        aliases.add(f"{prefix}{suffix}")
    if norm.lower().startswith("twenty-fivegige"):
        aliases.add(f"25GE{suffix}")
        aliases.add(f"GE{suffix}")
    elif norm.lower().startswith("hundredgige"):
        aliases.add(f"100GE{suffix}")
        aliases.add(f"HE{suffix}")
    return aliases


def _remap_config_usage(
    config_usage: dict[str, PortUsage],
    snmp_names: set[str],
) -> dict[str, PortUsage]:
    """Map running-config interface keys onto SNMP ifName values."""
    if not config_usage or not snmp_names:
        return config_usage

    snmp_by_suffix: dict[str, list[str]] = {}
    for name in snmp_names:
        suffix = _iface_port_suffix(name)
        if suffix:
            snmp_by_suffix.setdefault(suffix, []).append(name)

    remapped: dict[str, PortUsage] = {}
    for cfg_iface, usage in config_usage.items():
        target = cfg_iface if cfg_iface in snmp_names else None
        if target is None:
            for alias in _iface_aliases(cfg_iface):
                if alias in snmp_names:
                    target = alias
                    break
        if target is None:
            suffix = _iface_port_suffix(cfg_iface)
            if suffix and suffix in snmp_by_suffix:
                target = sorted(snmp_by_suffix[suffix])[0]
        if target is None:
            continue
        bucket = remapped.setdefault(target, PortUsage(interface_name=target))
        for entry in usage.entries:
            _merge_entries(bucket.entries, entry)
    return remapped


# ifAlias / description hints (operational tagging).
_DESC_SVID = re.compile(
    r"(?:s[- ]?vid|svlan|vlan|vid|dot1q)[:=\s]+(\d+)",
    re.IGNORECASE,
)
_DESC_QINQ = re.compile(
    r"[Ss]:(\d+)\s*/\s*[Cc]:(\d+)",
)
_DESC_SI = re.compile(
    r"service-instance\s+(\d+)",
    re.IGNORECASE,
)


def _parse_description_entries(text: str | None) -> list[SvidEntry]:
    if not text:
        return []
    entries: list[SvidEntry] = []
    if re.search(r"untagged|access\s+mode", text, re.I):
        entries.append(SvidEntry(s_vid=None, access_mode="access", source="device", note="ifAlias"))
    for m in _DESC_QINQ.finditer(text):
        entries.append(
            SvidEntry(
                s_vid=int(m.group(1)),
                c_vid=int(m.group(2)),
                access_mode="qinq",
                source="device",
                note="ifAlias",
            )
        )
    for m in _DESC_SVID.finditer(text):
        svid = int(m.group(1))
        if not any(e.s_vid == svid for e in entries):
            entries.append(
                SvidEntry(s_vid=svid, access_mode="dot1q", source="device", note="ifAlias")
            )
    for m in _DESC_SI.finditer(text):
        svid = int(m.group(1))
        if not any(e.s_vid == svid for e in entries):
            entries.append(
                SvidEntry(s_vid=svid, access_mode="dot1q", source="device", note="ifAlias")
            )
    return entries


def interface_description_usage(db: Session, device: Device) -> dict[str, PortUsage]:
    """Derive S-VID hints from persisted IF-MIB ifAlias / descriptions."""
    rows = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    by_iface: dict[str, PortUsage] = {}
    for iface in rows:
        entries = _parse_description_entries(iface.description)
        if not entries:
            continue
        usage = PortUsage(interface_name=iface.name)
        for entry in entries:
            _merge_entries(usage.entries, entry)
        by_iface[iface.name] = usage
    return by_iface


def _merge_entries(existing: list[SvidEntry], new: SvidEntry) -> None:
    keys = {e.key() for e in existing}
    if new.key() not in keys:
        existing.append(new)


def platform_usage(db: Session, device: Device) -> dict[str, PortUsage]:
    """Collect S-VID reservations from circuit endpoints in the platform DB."""
    rows = db.execute(
        select(CircuitEndpoint, Circuit)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(
            CircuitEndpoint.device_id == device.id,
            Circuit.status.in_(RESERVING_STATUSES),
        )
    ).all()

    by_iface: dict[str, PortUsage] = {}
    for ep, circuit in rows:
        iface = _normalize_iface(ep.interface_name)
        usage = by_iface.setdefault(iface, PortUsage(interface_name=iface))
        mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
        svid = ep.vlan_id or circuit.vlan_id
        if mode == AccessMode.ACCESS.value:
            _merge_entries(
                usage.entries,
                SvidEntry(
                    s_vid=None,
                    access_mode=mode,
                    circuit_code=circuit.code,
                    source="platform",
                ),
            )
        elif svid is not None:
            _merge_entries(
                usage.entries,
                SvidEntry(
                    s_vid=svid,
                    c_vid=ep.inner_vlan_id,
                    access_mode=mode,
                    circuit_code=circuit.code,
                    source="platform",
                ),
            )
    return by_iface


def _parse_h3c_block(iface: str, block: str) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    for m in re.finditer(
        r"service-instance\s+(\d+).*?"
        r"(encapsulation\s+untagged|encapsulation\s+s-vid\s+(\d+)(?:\s+c-vid\s+(\d+))?)",
        block,
        re.DOTALL | re.IGNORECASE,
    ):
        enc = m.group(2).lower()
        if "untagged" in enc:
            entries.append(SvidEntry(s_vid=None, access_mode="access", source="device"))
        else:
            entries.append(
                SvidEntry(
                    s_vid=int(m.group(3)),
                    c_vid=int(m.group(4)) if m.group(4) else None,
                    access_mode="qinq" if m.group(4) else "dot1q",
                    source="device",
                )
            )
    return entries


def _parse_huawei_block(iface: str, block: str) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    if re.search(r"encapsulation\s+untag", block, re.I):
        entries.append(SvidEntry(s_vid=None, access_mode="access", source="device"))
    for m in re.finditer(
        r"encapsulation\s+qinq\s+vid\s+(\d+)\s+ce-vid\s+(\d+)", block, re.I
    ):
        entries.append(
            SvidEntry(
                s_vid=int(m.group(1)),
                c_vid=int(m.group(2)),
                access_mode="qinq",
                source="device",
            )
        )
    for m in re.finditer(r"encapsulation\s+dot1q\s+vid\s+(\d+)", block, re.I):
        entries.append(
            SvidEntry(s_vid=int(m.group(1)), access_mode="dot1q", source="device")
        )
    return entries


def _parse_cisco_block(iface: str, block: str) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    if not re.search(r"\bl2transport\b", block, re.I):
        return entries
    if re.search(r"encapsulation\s+untagged", block, re.I):
        entries.append(SvidEntry(s_vid=None, access_mode="access", source="device"))
    for m in re.finditer(
        r"encapsulation\s+dot1q\s+(\d+)\s+second-dot1q\s+(\d+)", block, re.I
    ):
        entries.append(
            SvidEntry(
                s_vid=int(m.group(1)),
                c_vid=int(m.group(2)),
                access_mode="qinq",
                source="device",
            )
        )
    for m in re.finditer(r"encapsulation\s+dot1q\s+(\d+)", block, re.I):
        svid = int(m.group(1))
        if not any(e.s_vid == svid and e.access_mode == "dot1q" for e in entries):
            entries.append(SvidEntry(s_vid=svid, access_mode="dot1q", source="device"))
    return entries


def _parse_juniper_config(config: str) -> dict[str, list[SvidEntry]]:
    by_iface: dict[str, list[SvidEntry]] = {}
    for m in re.finditer(
        r"set interfaces (\S+) unit 0 vlan-tags outer (\d+) inner (\d+)", config
    ):
        iface = m.group(1)
        by_iface.setdefault(iface, []).append(
            SvidEntry(
                s_vid=int(m.group(2)),
                c_vid=int(m.group(3)),
                access_mode="qinq",
                source="device",
            )
        )
    for m in re.finditer(r"set interfaces (\S+) unit 0 vlan-id (\d+)", config):
        iface = m.group(1)
        svid = int(m.group(2))
        existing = by_iface.setdefault(iface, [])
        if not any(e.s_vid == svid for e in existing):
            existing.append(SvidEntry(s_vid=svid, access_mode="dot1q", source="device"))
    return by_iface


def _parse_interface_blocks(config: str, vendor: Vendor) -> dict[str, list[SvidEntry]]:
    """Parse vendor running-config text into per-interface S-VID usage."""
    if vendor == Vendor.JUNIPER:
        return _parse_juniper_config(config)

    by_iface: dict[str, list[SvidEntry]] = {}
    for m in re.finditer(
        r"^interface\s+(\S+)\s*$(.+?)(?=^interface\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = _normalize_iface(m.group(1))
        block = m.group(2)
        if vendor == Vendor.H3C:
            entries = _parse_h3c_block(iface, block)
        elif vendor == Vendor.HUAWEI:
            entries = _parse_huawei_block(iface, block)
        elif vendor == Vendor.CISCO:
            entries = _parse_cisco_block(iface, block)
        else:
            entries = (
                _parse_h3c_block(iface, block)
                or _parse_huawei_block(iface, block)
                or _parse_cisco_block(iface, block)
            )
        if entries:
            by_iface[iface] = entries
    return by_iface


def device_config_usage(db: Session, device: Device) -> dict[str, PortUsage]:
    """Parse device running-config for S-VID usage (learned snapshot preferred)."""
    learned = config_mgmt.latest_learned(db, device.id)
    config = learned.content if learned else config_mgmt.build_running_config(db, device)
    parsed = _parse_interface_blocks(config, device.vendor)
    by_iface: dict[str, PortUsage] = {}
    for iface, entries in parsed.items():
        usage = PortUsage(interface_name=iface)
        for e in entries:
            _merge_entries(usage.entries, e)
        by_iface[iface] = usage
    return by_iface


def legacy_simulated_usage(device: Device) -> dict[str, PortUsage]:
    """Inject demo legacy VLANs not tracked by the platform."""
    rows = _LEGACY_SIM.get(device.name, [])
    by_iface: dict[str, PortUsage] = {}
    for row in rows:
        iface = _normalize_iface(row["interface"])
        usage = by_iface.setdefault(iface, PortUsage(interface_name=iface))
        _merge_entries(
            usage.entries,
            SvidEntry(
                s_vid=row.get("s_vid"),
                c_vid=row.get("c_vid"),
                access_mode=row.get("access_mode", "dot1q"),
                source="legacy",
                note=row.get("note"),
            ),
        )
    return by_iface


def merge_port_maps(*maps: dict[str, PortUsage]) -> dict[str, PortUsage]:
    merged: dict[str, PortUsage] = {}
    for m in maps:
        for iface, usage in m.items():
            target = merged.setdefault(iface, PortUsage(interface_name=iface))
            for entry in usage.entries:
                _merge_entries(target.entries, entry)
    return merged


def scan_device(db: Session, device: Device, *, include_legacy: bool = True) -> dict:
    """Scan and persist S-VID inventory for a device. Returns summary for API."""
    ifaces = {
        i.name: i
        for i in db.execute(
            select(DeviceInterface).where(DeviceInterface.device_id == device.id)
        ).scalars().all()
    }
    snmp_names = set(ifaces.keys())

    plat = platform_usage(db, device)
    dev_raw = device_config_usage(db, device)
    dev = _remap_config_usage(dev_raw, snmp_names) if snmp_names else dev_raw
    desc = interface_description_usage(db, device)
    legacy = legacy_simulated_usage(device) if include_legacy else {}
    combined = merge_port_maps(plat, dev, desc, legacy)

    updated = 0
    port_summaries: list[dict] = []
    for iface_name, usage in sorted(combined.items()):
        serialized = [e.as_dict() for e in usage.entries]
        di = ifaces.get(iface_name)
        if di is None:
            di = DeviceInterface(device_id=device.id, name=iface_name, discovered_via="running-config")
            db.add(di)
            ifaces[iface_name] = di
        di.used_s_vids = serialized
        di.allocated = usage.allocated
        updated += 1
        port_summaries.append({
            "interface": iface_name,
            "allocated": usage.allocated,
            "s_vids": serialized,
        })

    # Clear stale inventory only when we had config/description data to reconcile.
    if combined:
        for name, di in ifaces.items():
            if name not in combined and di.used_s_vids:
                di.used_s_vids = []
                di.allocated = False
                updated += 1

    conflicts = find_conflicts(combined)
    return {
        "device": device.name,
        "ports_scanned": len(combined),
        "ports_updated": updated,
        "total_s_vids": sum(len(u.entries) for u in combined.values()),
        "conflicts": conflicts,
        "ports": port_summaries,
    }


def list_port_bindings(db: Session, device: Device) -> dict:
    """List customer/circuit bindings and device-only S-VID occupancy per interface."""
    rows = db.execute(
        select(CircuitEndpoint, Circuit, Tenant)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .join(Tenant, Tenant.id == Circuit.tenant_id)
        .where(CircuitEndpoint.device_id == device.id)
        .order_by(CircuitEndpoint.interface_name, Circuit.code)
    ).all()

    items: list[dict] = []
    platform_keys: set[tuple] = set()
    for ep, circuit, tenant in rows:
        mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
        svid = ep.vlan_id or circuit.vlan_id
        platform_keys.add(
            (_normalize_iface(ep.interface_name), mode, svid, ep.inner_vlan_id)
        )
        items.append({
            "interface_name": _normalize_iface(ep.interface_name),
            "binding_type": "platform",
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_code": tenant.code,
            "circuit_id": circuit.id,
            "circuit_code": circuit.code,
            "circuit_name": circuit.name,
            "circuit_status": circuit.status.value,
            "endpoint_label": ep.label,
            "access_mode": mode,
            "s_vid": svid,
            "c_vid": ep.inner_vlan_id,
            "vni": circuit.vni,
            "bandwidth_mbps": circuit.bandwidth_mbps,
            "source": "platform",
            "note": None,
        })

    ifaces = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    snmp_names = {i.name for i in ifaces}
    for iface in ifaces:
        for raw in iface.used_s_vids or []:
            if raw.get("source") == "platform":
                continue
            mode = raw.get("access_mode") or "dot1q"
            svid = raw.get("s_vid")
            cvid = raw.get("c_vid")
            key = (_normalize_iface(iface.name), mode, svid, cvid)
            if key in platform_keys:
                continue
            items.append({
                "interface_name": _normalize_iface(iface.name),
                "binding_type": "device",
                "tenant_id": None,
                "tenant_name": None,
                "tenant_code": None,
                "circuit_id": None,
                "circuit_code": raw.get("circuit_code"),
                "circuit_name": None,
                "circuit_status": None,
                "endpoint_label": None,
                "access_mode": mode,
                "s_vid": svid,
                "c_vid": cvid,
                "vni": None,
                "bandwidth_mbps": None,
                "source": raw.get("source") or "device",
                "note": raw.get("note"),
            })

    items.sort(key=lambda row: (row["interface_name"], row["binding_type"], row["s_vid"] or 0))
    bound_ifaces = {row["interface_name"] for row in items}
    unbound_ifaces = sorted(snmp_names - bound_ifaces) if snmp_names else []

    return {
        "device_id": device.id,
        "device": device.name,
        "total_bindings": len(items),
        "platform_bindings": sum(1 for row in items if row["binding_type"] == "platform"),
        "device_only_bindings": sum(1 for row in items if row["binding_type"] == "device"),
        "bound_interfaces": len(bound_ifaces),
        "unbound_interfaces": unbound_ifaces,
        "items": items,
    }


def find_conflicts(by_iface: dict[str, PortUsage]) -> list[dict]:
    """Detect duplicate S-VID on the same physical port."""
    issues: list[dict] = []
    for iface, usage in by_iface.items():
        seen: dict[tuple, SvidEntry] = {}
        for entry in usage.entries:
            key = entry.key()
            if key in seen:
                prev = seen[key]
                issues.append({
                    "interface": iface,
                    "s_vid": entry.s_vid,
                    "c_vid": entry.c_vid,
                    "access_mode": entry.access_mode,
                    "message": (
                        f"{iface} 上 S-VID {entry.s_vid or 'untagged'} 重复占用 "
                        f"({prev.source}/{prev.circuit_code or '-'} vs "
                        f"{entry.source}/{entry.circuit_code or '-'})"
                    ),
                })
            else:
                seen[key] = entry
        # Untagged fully occupies the port — warn if other VLANs also present.
        has_untag = any(e.access_mode == "access" for e in usage.entries)
        has_tagged = any(e.access_mode != "access" for e in usage.entries)
        if has_untag and has_tagged:
            issues.append({
                "interface": iface,
                "message": f"{iface} 同时存在 untagged 与 dot1q/qinq 封装，存在冲突风险",
            })
    return issues


def check_endpoint_available(
    db: Session,
    device_id: int,
    interface_name: str,
    vlan_id: int | None,
    inner_vlan_id: int | None = None,
    access_mode: AccessMode = AccessMode.DOT1Q,
    *,
    exclude_circuit_id: int | None = None,
) -> tuple[bool, str | None]:
    """Return (ok, error_message) for a proposed endpoint S-VID assignment."""
    device = db.get(Device, device_id)
    if not device:
        return False, "设备不存在"

    iface = _normalize_iface(interface_name)
    rows = db.execute(
        select(CircuitEndpoint, Circuit)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .where(
            CircuitEndpoint.device_id == device_id,
            CircuitEndpoint.interface_name == iface,
            Circuit.status.in_(RESERVING_STATUSES),
        )
    ).all()

    proposed = SvidEntry(
        s_vid=vlan_id if access_mode != AccessMode.ACCESS else None,
        c_vid=inner_vlan_id,
        access_mode=access_mode.value,
    )

    existing_entries: list[SvidEntry] = []
    for ep, circuit in rows:
        if exclude_circuit_id and circuit.id == exclude_circuit_id:
            continue
        mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
        svid = ep.vlan_id or circuit.vlan_id
        if mode == AccessMode.ACCESS.value:
            existing_entries.append(
                SvidEntry(s_vid=None, access_mode=mode, circuit_code=circuit.code)
            )
        elif svid is not None:
            existing_entries.append(
                SvidEntry(
                    s_vid=svid,
                    c_vid=ep.inner_vlan_id,
                    access_mode=mode,
                    circuit_code=circuit.code,
                )
            )

    # Include persisted device scan results (legacy/manual config).
    di = db.execute(
        select(DeviceInterface).where(
            DeviceInterface.device_id == device_id,
            DeviceInterface.name == iface,
        )
    ).scalar_one_or_none()
    if di and di.used_s_vids:
        for row in di.used_s_vids:
            if row.get("source") == "platform":
                continue
            existing_entries.append(
                SvidEntry(
                    s_vid=row.get("s_vid"),
                    c_vid=row.get("c_vid"),
                    access_mode=row.get("access_mode", "dot1q"),
                    circuit_code=row.get("circuit_code"),
                    source=row.get("source", "device"),
                )
            )

    usage = PortUsage(interface_name=iface, entries=list(existing_entries))

    # Exact encapsulation match already present?
    for entry in usage.entries:
        if entry.key() == proposed.key():
            who = entry.circuit_code or entry.source or "unknown"
            if entry.access_mode == "access":
                return False, f"{iface} 已配置 untagged 接入 (来源: {who})"
            if entry.c_vid:
                return False, (
                    f"{iface} 上 QinQ S-VID {entry.s_vid}/C-VID {entry.c_vid} "
                    f"已被占用 (来源: {who})"
                )
            return False, f"{iface} 上 S-VID {entry.s_vid} 已被占用 (来源: {who})"

    # Untagged occupies the whole port.
    if proposed.access_mode == "access" and usage.entries:
        return False, f"{iface} 已有 VLAN 封装，无法再配置 untagged 接入"
    if proposed.access_mode != "access" and any(
        e.access_mode == "access" for e in usage.entries
    ):
        return False, f"{iface} 已配置 untagged 接入，无法再叠加 VLAN"

    return True, None
