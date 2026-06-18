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
    description: str | None = None
    rate_limit_mbps: int | None = None
    vni: int | None = None
    vsi_name: str | None = None
    bridge_domain: str | None = None
    tenant_name: str | None = None
    tenant_code: str | None = None
    circuit_name: str | None = None
    bandwidth_mbps: int | None = None

    def as_dict(self) -> dict:
        return {
            "s_vid": self.s_vid,
            "c_vid": self.c_vid,
            "access_mode": self.access_mode,
            "circuit_code": self.circuit_code,
            "source": self.source,
            "note": self.note,
            "description": self.description,
            "rate_limit_mbps": self.rate_limit_mbps,
            "vni": self.vni,
            "vsi_name": self.vsi_name,
            "bridge_domain": self.bridge_domain,
            "tenant_name": self.tenant_name,
            "tenant_code": self.tenant_code,
            "circuit_name": self.circuit_name,
            "bandwidth_mbps": self.bandwidth_mbps,
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


_HUAWEI_SUBIF = re.compile(r"^(.+)\.(\d+)$")


def is_huawei_subinterface(name: str) -> bool:
    """True for Huawei L2 sub-interfaces like GE1/0/1.1050 or 10GE1/0/2.2001."""
    return parse_huawei_subinterface(name) is not None


def parse_huawei_subinterface(name: str) -> tuple[str, int] | None:
    """Split Huawei sub-interface into parent physical port and VLAN id."""
    norm = _normalize_iface(name)
    m = _HUAWEI_SUBIF.match(norm)
    if not m:
        return None
    parent, vlan_s = m.group(1), m.group(2)
    if not _iface_port_suffix(parent) and not re.search(r"\d+/\d+", parent):
        return None
    return parent, int(vlan_s)


def huawei_physical_port(name: str) -> str:
    """Map Huawei sub-interface names onto their parent physical port."""
    parts = parse_huawei_subinterface(name)
    return parts[0] if parts else _normalize_iface(name)


_SKIP_IFACE_RE = re.compile(
    r"^(loopback|vlanif|null|meth|inloopback|register-tunnel|vbdif)",
    re.IGNORECASE,
)
_VLAN_IFACE_RE = re.compile(
    r"^(?:Vlan-interface|Vlanif|VlanIF|Vlan)\d+$",
    re.IGNORECASE,
)
_VLAN_IFACE_LINE = re.compile(
    r"^interface\s+(Vlan-interface\d+|Vlanif\d+|VlanIF\d+|Vlan\d+)\s*$",
    re.IGNORECASE,
)


def is_vlan_interface_name(name: str) -> bool:
    """True for backbone L3 VLAN interfaces (H3C Vlan-interface, Huawei Vlanif)."""
    return bool(_VLAN_IFACE_RE.match(_normalize_iface(name)))


def list_vlan_interfaces_from_config(config: str, vendor: Vendor) -> list[dict]:
    """Extract L3 VLAN interfaces from running-config for backbone link planning."""
    del vendor  # naming is shared across H3C / Huawei
    results: list[dict] = []
    lines = config.splitlines()
    idx = 0
    while idx < len(lines):
        match = _VLAN_IFACE_LINE.match(lines[idx].strip())
        if not match:
            idx += 1
            continue
        name = _normalize_iface(match.group(1))
        description: str | None = None
        idx += 1
        while idx < len(lines):
            stripped = lines[idx].strip()
            if not stripped or stripped == "#":
                idx += 1
                break
            if _VLAN_IFACE_LINE.match(stripped) or re.match(
                r"^interface\s+\S+", stripped, re.IGNORECASE
            ):
                break
            desc_match = re.match(r"^description\s+(.+)$", stripped, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1).strip()
            idx += 1
        results.append({"name": name, "description": description})
    return results


def list_physical_interfaces_from_config(config: str, vendor: Vendor) -> list[str]:
    """Extract physical port names from running-config when SNMP is unavailable."""
    names: set[str] = set()
    for m in re.finditer(
        r"^interface\s+(\S+)(?:\s+mode\s+\S+)?\s*$",
        config,
        re.MULTILINE | re.IGNORECASE,
    ):
        raw = _normalize_iface(m.group(1))
        if vendor == Vendor.HUAWEI and is_huawei_subinterface(raw):
            names.add(huawei_physical_port(raw))
            continue
        if is_vlan_interface_name(raw) or _SKIP_IFACE_RE.match(raw):
            continue
        if vendor == Vendor.HUAWEI and not re.search(r"\d+/\d+", raw):
            continue
        names.add(raw)
    return sorted(names)


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


def _pick_canonical_snmp_name(names: list[str]) -> str:
    """Pick one SNMP ifName when several aliases share the same port suffix."""

    def _score(name: str) -> tuple[int, int, str]:
        lower = name.lower()
        if lower.startswith(("twenty-fivegige", "hundredgige", "tengigabitethernet")):
            return (0, len(name), name)
        if lower.startswith(("gigabitethernet", "ge", "25ge", "100ge", "10ge")):
            return (1, len(name), name)
        return (2, len(name), name)

    return sorted(names, key=_score)[0]


def _build_alias_map(snmp_names: set[str]) -> dict[str, str]:
    """Map CLI/platform interface aliases onto canonical SNMP ifName values."""
    suffix_to_snmp: dict[str, list[str]] = {}
    for name in snmp_names:
        suffix = _iface_port_suffix(name)
        if suffix:
            suffix_to_snmp.setdefault(suffix, []).append(name)

    alias_to_canonical: dict[str, str] = {}
    for suffix, names in suffix_to_snmp.items():
        canonical = _pick_canonical_snmp_name(names)
        for alias in _iface_aliases(canonical):
            alias_to_canonical.setdefault(alias, canonical)
    for name in snmp_names:
        alias_to_canonical.setdefault(name, name)
        for alias in _iface_aliases(name):
            alias_to_canonical.setdefault(alias, name)
    return alias_to_canonical


def _build_iface_resolver(
    interfaces: list[DeviceInterface],
) -> tuple[set[str], dict[str, str]]:
    """Build SNMP name set and alias map from persisted interface rows."""
    snmp_rows = [
        i for i in interfaces if i.discovered_via == "snmp" or i.ifindex is not None
    ]
    snmp_names = {i.name for i in snmp_rows} or {i.name for i in interfaces}
    return snmp_names, _build_alias_map(snmp_names)


def _resolve_iface_name_direct(name: str, alias_to_canonical: dict[str, str]) -> str | None:
    norm = _normalize_iface(name)
    if norm in alias_to_canonical:
        return alias_to_canonical[norm]
    for alias in _iface_aliases(norm):
        if alias in alias_to_canonical:
            return alias_to_canonical[alias]
    suffix = _iface_port_suffix(norm)
    if suffix:
        for alias in _iface_aliases(f"GE{suffix}"):
            if alias in alias_to_canonical:
                return alias_to_canonical[alias]
    return None


def _resolve_iface_name(name: str, alias_to_canonical: dict[str, str]) -> str | None:
    """Resolve CLI/platform/config names onto canonical SNMP ifNames."""
    resolved = _resolve_iface_name_direct(name, alias_to_canonical)
    if resolved:
        return resolved
    parts = parse_huawei_subinterface(name)
    if parts:
        return _resolve_iface_name_direct(parts[0], alias_to_canonical)
    return None


def _rollup_huawei_subif_usage(by_iface: dict[str, PortUsage]) -> dict[str, PortUsage]:
    """Aggregate Huawei sub-interface VLAN bindings onto parent physical ports."""
    rolled: dict[str, PortUsage] = {}
    for iface, usage in by_iface.items():
        parent = huawei_physical_port(iface)
        bucket = rolled.setdefault(parent, PortUsage(interface_name=parent))
        for entry in usage.entries:
            _merge_entries(bucket.entries, entry)
    return rolled


def _canonical_iface_for_device(
    device: Device,
    name: str,
    alias_to_canonical: dict[str, str],
) -> str:
    lookup = huawei_physical_port(name) if device.vendor == Vendor.HUAWEI else name
    return _resolve_iface_name(lookup, alias_to_canonical) or lookup


def _remap_usage_map(
    usage_map: dict[str, PortUsage],
    alias_to_canonical: dict[str, str],
) -> dict[str, PortUsage]:
    """Map usage keys (platform/config/description) onto canonical SNMP ifNames."""
    if not usage_map or not alias_to_canonical:
        return usage_map

    remapped: dict[str, PortUsage] = {}
    for iface, usage in usage_map.items():
        target = _resolve_iface_name(iface, alias_to_canonical)
        if target is None:
            continue
        bucket = remapped.setdefault(target, PortUsage(interface_name=target))
        for entry in usage.entries:
            _merge_entries(bucket.entries, entry)
    return remapped


def _remap_config_usage(
    config_usage: dict[str, PortUsage],
    snmp_names: set[str],
) -> dict[str, PortUsage]:
    """Map running-config interface keys onto SNMP ifName values."""
    if not config_usage or not snmp_names:
        return config_usage
    return _remap_usage_map(config_usage, _build_alias_map(snmp_names))


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
    for entry in existing:
        if entry.key() == new.key():
            for field in (
                "circuit_code",
                "note",
                "description",
                "rate_limit_mbps",
                "vni",
                "vsi_name",
                "tenant_name",
                "tenant_code",
                "circuit_name",
                "bandwidth_mbps",
            ):
                incoming = getattr(new, field)
                if incoming and not getattr(entry, field):
                    setattr(entry, field, incoming)
            if new.source == "platform":
                entry.source = "platform"
            return
    existing.append(new)


def _parse_h3c_qos_policy_map(config: str) -> dict[str, int]:
    """Map H3C qos policy name -> CAR cir (kbps)."""
    behavior_cir: dict[str, int] = {}
    for m in re.finditer(
        r"^traffic behavior\s+(\S+)\s*$(.+?)(?=^traffic behavior\s|^traffic classifier\s|^qos policy\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        car = re.search(r"car\s+cir\s+(\d+)", m.group(2), re.I)
        if car:
            behavior_cir[m.group(1)] = int(car.group(1))

    policy_kbps: dict[str, int] = {}
    for m in re.finditer(
        r"^qos policy\s+(\S+)\s*$(.+?)(?=^qos policy\s|^traffic behavior\s|^traffic classifier\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        behavior_m = re.search(r"classifier\s+\S+\s+behavior\s+(\S+)", m.group(2), re.I)
        if behavior_m and behavior_m.group(1) in behavior_cir:
            policy_kbps[m.group(1)] = behavior_cir[behavior_m.group(1)]
    return policy_kbps


def _parse_huawei_traffic_policy_map(config: str) -> dict[str, int]:
    """Map Huawei traffic policy name -> CAR cir (kbps)."""
    behavior_cir: dict[str, int] = {}
    for m in re.finditer(
        r"^traffic behavior\s+(\S+)\s*$(.+?)(?=^traffic behavior\s|^traffic classifier\s|^traffic policy\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        car = re.search(r"car\s+cir\s+(\d+)", m.group(2), re.I)
        if car:
            behavior_cir[m.group(1)] = int(car.group(1))

    policy_kbps: dict[str, int] = {}
    for m in re.finditer(
        r"^traffic policy\s+(\S+)\s*$(.+?)(?=^traffic policy\s|^traffic behavior\s|^traffic classifier\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        behavior_m = re.search(r"classifier\s+\S+\s+behavior\s+(\S+)", m.group(2), re.I)
        if behavior_m and behavior_m.group(1) in behavior_cir:
            policy_kbps[m.group(1)] = behavior_cir[behavior_m.group(1)]
    return policy_kbps


def _parse_rate_limit_kbps(text: str, *, policy_map: dict[str, int] | None = None) -> int | None:
    apply_m = re.search(r"qos\s+apply\s+policy\s+(\S+)", text, re.I)
    if apply_m and policy_map and apply_m.group(1) in policy_map:
        return policy_map[apply_m.group(1)]
    tp_m = re.search(r"traffic-policy\s+(\S+)", text, re.I)
    if tp_m and policy_map and tp_m.group(1) in policy_map:
        return policy_map[tp_m.group(1)]
    car = re.search(r"qos\s+car\s+inbound\s+any\s+cir\s+(\d+)", text, re.I)
    if car:
        return int(car.group(1))
    lr = re.search(r"qos\s+lr\s+cir\s+(\d+)", text, re.I)
    if lr:
        return int(lr.group(1))
    bw = re.search(r"bw\((\d+)\s*([MmGg])bps\)", text, re.I)
    if bw:
        value = int(bw.group(1))
        unit = bw.group(2).lower()
        if unit == "g":
            return value * 1_000_000
        return value * 1_000
    return None


def _kbps_to_mbps(kbps: int | None) -> int | None:
    if kbps is None:
        return None
    if kbps % 1024 == 0 and kbps >= 1024:
        return kbps // 1024
    return max(1, kbps // 1000) if kbps >= 1000 else 1


def _parse_huawei_bd_map(config: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(
        r"^bridge-domain\s+(\S+)\s*$(.+?)(?=^bridge-domain\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        bd = m.group(1)
        body = m.group(2)
        vni_m = re.search(r"vxlan\s+vni\s+(\d+)", body, re.I)
        rd_m = re.search(r"route-distinguisher\s+(\S+)", body, re.I)
        rt_m = re.search(r"vpn-target\s+(\S+)\s+import-extcommunity", body, re.I)
        desc_m = re.search(r"^\s*description\s+(.+)$", body, re.MULTILINE | re.IGNORECASE)
        out[bd] = {
            "vni": int(vni_m.group(1)) if vni_m else None,
            "rd": rd_m.group(1) if rd_m else None,
            "rt": rt_m.group(1) if rt_m else None,
            "description": desc_m.group(1).strip() if desc_m else None,
        }
    return out


def _parse_h3c_vsi_map(config: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(
        r"^vsi\s+(\S+)\s*$(.+?)(?=^vsi\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        name = m.group(1)
        body = m.group(2)
        vni_m = re.search(r"vxlan\s+(\d+)", body, re.I)
        desc_m = re.search(r"^\s*description\s+(.+)$", body, re.MULTILINE | re.IGNORECASE)
        out[name] = {
            "vni": int(vni_m.group(1)) if vni_m else None,
            "description": desc_m.group(1).strip() if desc_m else None,
        }
    return out


@dataclass
class _CircuitCatalog:
    by_vni: dict[int, Circuit]
    by_code: dict[str, Circuit]
    tenants: dict[int, Tenant]


def _build_circuit_catalog(db: Session) -> _CircuitCatalog:
    circuits = db.execute(select(Circuit)).scalars().all()
    tenants = {
        t.id: t for t in db.execute(select(Tenant)).scalars().all()
    }
    return _CircuitCatalog(
        by_vni={c.vni: c for c in circuits if c.vni is not None},
        by_code={c.code: c for c in circuits},
        tenants=tenants,
    )


def _apply_circuit_context(entry: SvidEntry, circuit: Circuit, catalog: _CircuitCatalog) -> None:
    entry.circuit_code = entry.circuit_code or circuit.code
    entry.circuit_name = entry.circuit_name or circuit.name
    entry.vni = entry.vni or circuit.vni
    entry.bandwidth_mbps = entry.bandwidth_mbps or circuit.bandwidth_mbps
    entry.vsi_name = entry.vsi_name or circuit.vsi_name
    tenant = catalog.tenants.get(circuit.tenant_id)
    if tenant:
        entry.tenant_name = entry.tenant_name or tenant.name
        entry.tenant_code = entry.tenant_code or tenant.code


def _infer_customer_from_text(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"cn\(([^)]+)\)", text, re.I)
    if match:
        return match.group(1).strip()
    if text.lower().startswith("cus-"):
        return text
    return None


def _enrich_svid_entry(
    entry: SvidEntry,
    *,
    catalog: _CircuitCatalog,
    vsi_map: dict[str, dict] | None = None,
    bd_map: dict[str, dict] | None = None,
) -> None:
    if entry.vsi_name and vsi_map and entry.vsi_name in vsi_map:
        meta = vsi_map[entry.vsi_name]
        entry.vni = entry.vni or meta.get("vni")
        entry.description = entry.description or meta.get("description")

    if entry.bridge_domain and bd_map and entry.bridge_domain in bd_map:
        meta = bd_map[entry.bridge_domain]
        entry.vni = entry.vni or meta.get("vni")
        entry.description = entry.description or meta.get("description")

    if entry.circuit_code and entry.circuit_code in catalog.by_code:
        _apply_circuit_context(entry, catalog.by_code[entry.circuit_code], catalog)
    elif entry.vni is not None and entry.vni in catalog.by_vni:
        _apply_circuit_context(entry, catalog.by_vni[entry.vni], catalog)

    if entry.rate_limit_mbps and not entry.bandwidth_mbps:
        entry.bandwidth_mbps = entry.rate_limit_mbps

    if not entry.tenant_name:
        entry.tenant_name = _infer_customer_from_text(entry.description) or _infer_customer_from_text(
            entry.vsi_name
        )


def platform_usage(db: Session, device: Device) -> dict[str, PortUsage]:
    """Collect S-VID reservations from circuit endpoints in the platform DB."""
    catalog = _build_circuit_catalog(db)
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
        tenant = catalog.tenants.get(circuit.tenant_id)
        entry = SvidEntry(
            s_vid=None if mode == AccessMode.ACCESS.value else svid,
            c_vid=ep.inner_vlan_id,
            access_mode=mode,
            circuit_code=circuit.code,
            source="platform",
            description=circuit.description or circuit.name,
            vni=circuit.vni,
            vsi_name=circuit.vsi_name,
            tenant_name=tenant.name if tenant else None,
            tenant_code=tenant.code if tenant else None,
            circuit_name=circuit.name,
            bandwidth_mbps=circuit.bandwidth_mbps,
            rate_limit_mbps=circuit.bandwidth_mbps,
        )
        _merge_entries(usage.entries, entry)
    return by_iface


def _parse_h3c_block(iface: str, block: str, policy_map: dict[str, int] | None = None) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    iface_desc_m = re.search(r"^\s*description\s+(.+)$", block, re.MULTILINE | re.IGNORECASE)
    iface_desc = iface_desc_m.group(1).strip() if iface_desc_m else None

    for m in re.finditer(
        r"service-instance\s+\d+\s*\n(.*?)(?=^\s*service-instance\s|\Z)",
        block,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        si_body = m.group(1)
        desc_m = re.search(r"^\s*description\s+(.+)$", si_body, re.MULTILINE | re.IGNORECASE)
        vsi_m = re.search(r"xconnect\s+vsi\s+(\S+)", si_body, re.I)
        rate_kbps = _parse_rate_limit_kbps(si_body, policy_map=policy_map)
        description = (desc_m.group(1).strip() if desc_m else None) or iface_desc

        if re.search(r"encapsulation\s+untagged", si_body, re.I):
            entries.append(
                SvidEntry(
                    s_vid=None,
                    access_mode="access",
                    source="device",
                    description=description,
                    rate_limit_mbps=_kbps_to_mbps(rate_kbps),
                    vsi_name=vsi_m.group(1) if vsi_m else None,
                )
            )
            continue

        qinq_m = re.search(
            r"encapsulation\s+s-vid\s+(\d+)\s+c-vid\s+(\d+)", si_body, re.I
        )
        if qinq_m:
            entries.append(
                SvidEntry(
                    s_vid=int(qinq_m.group(1)),
                    c_vid=int(qinq_m.group(2)),
                    access_mode="qinq",
                    source="device",
                    description=description,
                    rate_limit_mbps=_kbps_to_mbps(rate_kbps),
                    vsi_name=vsi_m.group(1) if vsi_m else None,
                )
            )
            continue

        dot1q_m = re.search(r"encapsulation\s+s-vid\s+(\d+)", si_body, re.I)
        if dot1q_m:
            entries.append(
                SvidEntry(
                    s_vid=int(dot1q_m.group(1)),
                    access_mode="dot1q",
                    source="device",
                    description=description,
                    rate_limit_mbps=_kbps_to_mbps(rate_kbps),
                    vsi_name=vsi_m.group(1) if vsi_m else None,
                )
            )
    return entries


def _parse_huawei_block(iface: str, block: str, policy_map: dict[str, int] | None = None) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    rate_kbps = _parse_rate_limit_kbps(block, policy_map=policy_map)
    rate_mbps = _kbps_to_mbps(rate_kbps)
    bd_m = re.search(r"bridge-domain\s+(\S+)", block, re.I)
    bridge_domain = bd_m.group(1) if bd_m else None
    if re.search(r"encapsulation\s+untag", block, re.I):
        entries.append(
            SvidEntry(
                s_vid=None,
                access_mode="access",
                source="device",
                rate_limit_mbps=rate_mbps,
                bridge_domain=bridge_domain,
            )
        )
    for m in re.finditer(
        r"encapsulation\s+qinq\s+vid\s+(\d+)\s+ce-vid\s+(\d+)", block, re.I
    ):
        entries.append(
            SvidEntry(
                s_vid=int(m.group(1)),
                c_vid=int(m.group(2)),
                access_mode="qinq",
                source="device",
                rate_limit_mbps=rate_mbps,
                bridge_domain=bridge_domain,
            )
        )
    for m in re.finditer(r"encapsulation\s+dot1q\s+vid\s+(\d+)", block, re.I):
        entries.append(
            SvidEntry(
                s_vid=int(m.group(1)),
                access_mode="dot1q",
                source="device",
                rate_limit_mbps=rate_mbps,
                bridge_domain=bridge_domain,
            )
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

    policy_map: dict[str, int] | None = None
    if vendor == Vendor.H3C:
        policy_map = _parse_h3c_qos_policy_map(config)
    elif vendor == Vendor.HUAWEI:
        policy_map = _parse_huawei_traffic_policy_map(config)

    by_iface: dict[str, list[SvidEntry]] = {}
    for m in re.finditer(
        r"^interface\s+(\S+)(?:\s+mode\s+\S+)?\s*$(.+?)(?=^interface\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = _normalize_iface(m.group(1))
        block = m.group(2)
        if vendor == Vendor.H3C:
            entries = _parse_h3c_block(iface, block, policy_map)
        elif vendor == Vendor.HUAWEI:
            entries = _parse_huawei_block(iface, block, policy_map)
        elif vendor == Vendor.CISCO:
            entries = _parse_cisco_block(iface, block)
        else:
            entries = (
                _parse_h3c_block(iface, block, policy_map)
                or _parse_huawei_block(iface, block, policy_map)
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
    if device.vendor == Vendor.HUAWEI:
        port_map = {
            iface: PortUsage(interface_name=iface, entries=entries)
            for iface, entries in parsed.items()
        }
        parsed = {
            iface: usage.entries
            for iface, usage in _rollup_huawei_subif_usage(port_map).items()
        }
    vsi_map = _parse_h3c_vsi_map(config) if device.vendor == Vendor.H3C else {}
    bd_map = _parse_huawei_bd_map(config) if device.vendor == Vendor.HUAWEI else {}
    catalog = _build_circuit_catalog(db)
    by_iface: dict[str, PortUsage] = {}
    for iface, entries in parsed.items():
        usage = PortUsage(interface_name=iface)
        for entry in entries:
            _enrich_svid_entry(
                entry,
                catalog=catalog,
                vsi_map=vsi_map or None,
                bd_map=bd_map or None,
            )
            _merge_entries(usage.entries, entry)
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


def _iface_row_rank(iface: DeviceInterface) -> tuple[int, int, str]:
    if iface.discovered_via == "snmp":
        return (0, iface.ifindex or 0, iface.name)
    if iface.ifindex is not None:
        return (1, iface.ifindex, iface.name)
    if iface.discovered_via == "running-config":
        return (2, 0, iface.name)
    return (3, 0, iface.name)


def _entries_from_json(rows: list | None) -> list[SvidEntry]:
    entries: list[SvidEntry] = []
    for raw in rows or []:
        entry = SvidEntry(
            s_vid=raw.get("s_vid"),
            c_vid=raw.get("c_vid"),
            access_mode=raw.get("access_mode", "dot1q"),
            circuit_code=raw.get("circuit_code"),
            source=raw.get("source", "device"),
            note=raw.get("note"),
            description=raw.get("description"),
            rate_limit_mbps=raw.get("rate_limit_mbps"),
            vni=raw.get("vni"),
            vsi_name=raw.get("vsi_name"),
            tenant_name=raw.get("tenant_name"),
            tenant_code=raw.get("tenant_code"),
            circuit_name=raw.get("circuit_name"),
            bandwidth_mbps=raw.get("bandwidth_mbps"),
        )
        _merge_entries(entries, entry)
    return entries


def _dedupe_device_interfaces(
    db: Session,
    device: Device,
    alias_to_canonical: dict[str, str],
) -> dict[str, DeviceInterface]:
    """Merge duplicate interface rows that refer to the same physical port."""
    rows = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()

    groups: dict[str, list[DeviceInterface]] = {}
    for row in rows:
        lookup = huawei_physical_port(row.name) if device.vendor == Vendor.HUAWEI else row.name
        canonical = _resolve_iface_name(lookup, alias_to_canonical) or lookup
        groups.setdefault(canonical, []).append(row)

    canonical_rows: dict[str, DeviceInterface] = {}
    for canonical, group in groups.items():
        group.sort(key=_iface_row_rank)
        keeper = next((row for row in group if row.name == canonical), group[0])
        merged_entries = _entries_from_json(keeper.used_s_vids)
        for orphan in group:
            if orphan is keeper:
                continue
            for entry in _entries_from_json(orphan.used_s_vids):
                _merge_entries(merged_entries, entry)
            if not keeper.description and orphan.description:
                keeper.description = orphan.description
            if keeper.speed_mbps is None and orphan.speed_mbps is not None:
                keeper.speed_mbps = orphan.speed_mbps
            if keeper.ifindex is None and orphan.ifindex is not None:
                keeper.ifindex = orphan.ifindex
            if keeper.oper_status is None and orphan.oper_status is not None:
                keeper.oper_status = orphan.oper_status
            if orphan.discovered_via == "snmp" and keeper.discovered_via != "snmp":
                keeper.discovered_via = orphan.discovered_via
            db.delete(orphan)
        keeper.used_s_vids = [e.as_dict() for e in merged_entries]
        keeper.allocated = bool(merged_entries)
        canonical_rows[canonical] = keeper
    return canonical_rows


def _reconcile_endpoint_names(
    db: Session,
    device: Device,
    alias_to_canonical: dict[str, str],
) -> int:
    """Rewrite circuit endpoint interface names to canonical SNMP ifNames."""
    rows = db.execute(
        select(CircuitEndpoint).where(CircuitEndpoint.device_id == device.id)
    ).scalars().all()
    updated = 0
    for ep in rows:
        canonical = _resolve_iface_name(ep.interface_name, alias_to_canonical)
        if canonical and canonical != ep.interface_name:
            ep.interface_name = canonical
            updated += 1
    return updated


def _cleanup_huawei_subif_rows(
    db: Session,
    ifaces: dict[str, DeviceInterface],
    alias_to_canonical: dict[str, str],
) -> int:
    """Remove merged Huawei sub-interface rows after rollup onto physical ports."""
    removed = 0
    for name in list(ifaces.keys()):
        parts = parse_huawei_subinterface(name)
        if not parts:
            continue
        parent = _resolve_iface_name(parts[0], alias_to_canonical) or parts[0]
        if parent == name:
            continue
        sub_row = ifaces.get(name)
        parent_row = ifaces.get(parent)
        if not sub_row or not parent_row:
            continue
        merged_entries = _entries_from_json(parent_row.used_s_vids)
        for entry in _entries_from_json(sub_row.used_s_vids):
            _merge_entries(merged_entries, entry)
        parent_row.used_s_vids = [e.as_dict() for e in merged_entries]
        parent_row.allocated = parent_row.allocated or sub_row.allocated
        db.delete(sub_row)
        del ifaces[name]
        removed += 1
    return removed


def scan_device(db: Session, device: Device, *, include_legacy: bool = False) -> dict:
    """Scan and persist S-VID inventory for a device. Returns summary for API."""
    iface_rows = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    snmp_names, alias_to_canonical = _build_iface_resolver(iface_rows)
    ifaces = _dedupe_device_interfaces(db, device, alias_to_canonical)
    endpoints_reconciled = _reconcile_endpoint_names(db, device, alias_to_canonical)

    plat = _remap_usage_map(platform_usage(db, device), alias_to_canonical)
    dev_raw = device_config_usage(db, device)
    dev = _remap_config_usage(dev_raw, snmp_names) if snmp_names else dev_raw
    desc = _remap_usage_map(interface_description_usage(db, device), alias_to_canonical)
    legacy = _remap_usage_map(
        legacy_simulated_usage(device) if include_legacy else {},
        alias_to_canonical,
    )
    combined = merge_port_maps(plat, dev, desc, legacy)

    updated = 0
    port_summaries: list[dict] = []
    for iface_name, usage in sorted(combined.items()):
        serialized = [e.as_dict() for e in usage.entries]
        di = ifaces.get(iface_name)
        if di is None:
            if snmp_names and _resolve_iface_name(iface_name, alias_to_canonical) is None:
                continue
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

    if device.vendor == Vendor.HUAWEI:
        updated += _cleanup_huawei_subif_rows(db, ifaces, alias_to_canonical)

    conflicts = find_conflicts(combined)
    return {
        "device": device.name,
        "ports_scanned": len(combined),
        "ports_updated": updated,
        "endpoints_reconciled": endpoints_reconciled,
        "total_s_vids": sum(len(u.entries) for u in combined.values()),
        "conflicts": conflicts,
        "ports": port_summaries,
    }


def list_port_bindings(db: Session, device: Device) -> dict:
    """Customer · interface · service relationship rows (one per S-VID binding)."""
    catalog = _build_circuit_catalog(db)
    items: list[dict] = []
    seen_keys: set[tuple] = set()

    def _binding_key(
        iface: str, mode: str, svid: int | None, cvid: int | None
    ) -> tuple:
        return (_normalize_iface(iface), mode, svid, cvid)

    def _append_row(
        *,
        interface_name: str,
        raw: dict,
        binding_type: str,
        circuit: Circuit | None = None,
        tenant: Tenant | None = None,
        endpoint_label: str | None = None,
    ) -> None:
        mode = raw.get("access_mode") or "dot1q"
        svid = raw.get("s_vid")
        cvid = raw.get("c_vid")
        key = _binding_key(interface_name, mode, svid, cvid)
        if key in seen_keys:
            return
        seen_keys.add(key)

        if circuit is None and raw.get("circuit_code"):
            circuit = catalog.by_code.get(raw["circuit_code"])
        if circuit is None and raw.get("vni") is not None:
            circuit = catalog.by_vni.get(raw["vni"])
        if tenant is None and circuit is not None:
            tenant = catalog.tenants.get(circuit.tenant_id)

        tenant_name = raw.get("tenant_name") or (tenant.name if tenant else None)
        tenant_code = raw.get("tenant_code") or (tenant.code if tenant else None)
        circuit_name = raw.get("circuit_name") or (circuit.name if circuit else None)
        circuit_code = raw.get("circuit_code") or (circuit.code if circuit else None)
        rate = raw.get("rate_limit_mbps") or raw.get("bandwidth_mbps")
        if rate is None and circuit is not None:
            rate = circuit.bandwidth_mbps
        business_name = (
            circuit_name
            or raw.get("vsi_name")
            or raw.get("description")
            or circuit_code
        )

        items.append({
            "interface_name": _normalize_iface(interface_name),
            "binding_type": binding_type,
            "tenant_id": tenant.id if tenant else None,
            "tenant_name": tenant_name,
            "tenant_code": tenant_code,
            "business_name": business_name,
            "circuit_id": circuit.id if circuit else None,
            "circuit_code": circuit_code,
            "circuit_name": circuit_name,
            "circuit_status": circuit.status.value if circuit else None,
            "endpoint_label": endpoint_label,
            "access_mode": mode,
            "s_vid": svid,
            "c_vid": cvid,
            "vni": raw.get("vni") or (circuit.vni if circuit else None),
            "vsi_name": raw.get("vsi_name") or (circuit.vsi_name if circuit else None),
            "description": raw.get("description"),
            "rate_limit_mbps": raw.get("rate_limit_mbps"),
            "bandwidth_mbps": rate,
            "source": raw.get("source") or ("platform" if circuit else "device"),
            "note": raw.get("note"),
        })

    ifaces = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device.id)
    ).scalars().all()
    snmp_names, alias_to_canonical = _build_iface_resolver(ifaces)

    def _canonical_iface(name: str) -> str:
        return _canonical_iface_for_device(device, name, alias_to_canonical)

    for iface in ifaces:
        canonical = _canonical_iface(iface.name)
        for raw in iface.used_s_vids or []:
            btype = "platform" if raw.get("source") == "platform" else "device"
            _append_row(
                interface_name=canonical,
                raw=raw,
                binding_type=btype,
            )

    rows = db.execute(
        select(CircuitEndpoint, Circuit, Tenant)
        .join(Circuit, Circuit.id == CircuitEndpoint.circuit_id)
        .join(Tenant, Tenant.id == Circuit.tenant_id)
        .where(CircuitEndpoint.device_id == device.id)
        .order_by(CircuitEndpoint.interface_name, Circuit.code)
    ).all()

    for ep, circuit, tenant in rows:
        mode = ep.access_mode.value if ep.access_mode else AccessMode.DOT1Q.value
        svid = ep.vlan_id or circuit.vlan_id
        key = _binding_key(_canonical_iface(ep.interface_name), mode, svid, ep.inner_vlan_id)
        if key in seen_keys:
            continue
        _append_row(
            interface_name=_canonical_iface(ep.interface_name),
            raw={
                "s_vid": svid,
                "c_vid": ep.inner_vlan_id,
                "access_mode": mode,
                "circuit_code": circuit.code,
                "circuit_name": circuit.name,
                "tenant_name": tenant.name,
                "tenant_code": tenant.code,
                "vni": circuit.vni,
                "vsi_name": circuit.vsi_name,
                "bandwidth_mbps": circuit.bandwidth_mbps,
                "description": circuit.description or circuit.name,
                "source": "platform",
            },
            binding_type="platform",
            circuit=circuit,
            tenant=tenant,
            endpoint_label=ep.label,
        )

    items.sort(
        key=lambda row: (
            row.get("tenant_name") or "zzz",
            row["interface_name"],
            row.get("s_vid") or 0,
        )
    )
    bound_ifaces = {row["interface_name"] for row in items}
    snmp_physical = (
        {n for n in snmp_names if not is_huawei_subinterface(n)}
        if device.vendor == Vendor.HUAWEI
        else snmp_names
    )
    unbound_ifaces = sorted(snmp_physical - bound_ifaces) if snmp_physical else []

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
    iface_rows = db.execute(
        select(DeviceInterface).where(DeviceInterface.device_id == device_id)
    ).scalars().all()
    _, alias_to_canonical = _build_iface_resolver(iface_rows)
    resolved = _resolve_iface_name(iface, alias_to_canonical)
    if resolved:
        iface = resolved

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
