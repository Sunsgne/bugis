"""Parse live running-config into structured inventory for platform features."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import Vendor


@dataclass
class L2Service:
    name: str
    vni: int | None = None
    rd: str | None = None
    rt: str | None = None
    service_type: str = "l2vpn_evpn"
    interfaces: list[str] = field(default_factory=list)
    vlans: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "vni": self.vni,
            "rd": self.rd,
            "rt": self.rt,
            "service_type": self.service_type,
            "interfaces": self.interfaces,
            "vlans": self.vlans,
        }


@dataclass
class LearnedInventory:
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    bgp_router_id: str | None = None
    l2_services: list[L2Service] = field(default_factory=list)
    interface_count: int = 0
    vlan_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "loopback_ip": self.loopback_ip,
            "bgp_asn": self.bgp_asn,
            "bgp_router_id": self.bgp_router_id,
            "l2_services": [s.as_dict() for s in self.l2_services],
            "interface_count": self.interface_count,
            "vlan_ids": sorted(set(self.vlan_ids)),
            "service_count": len(self.l2_services),
        }


def _parse_loopback(config: str, vendor: Vendor) -> str | None:
    if vendor == Vendor.JUNIPER:
        m = re.search(r"set interfaces lo0 unit 0 family inet address (\S+)/", config)
        return m.group(1) if m else None
    patterns = [
        r"interface LoopBack0\s*\n\s*ip address (\d+\.\d+\.\d+\.\d+)",
        r"interface Loopback0\s*\n\s*ipv4 address (\d+\.\d+\.\d+\.\d+)",
        r"LoopBack0.*?ip address (\d+\.\d+\.\d+\.\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, config, re.I | re.DOTALL)
        if m:
            return m.group(1)
    return None


def _parse_bgp_asn(config: str, vendor: Vendor) -> tuple[int | None, str | None]:
    if vendor == Vendor.JUNIPER:
        m = re.search(r"set routing-options autonomous-system (\d+)", config)
        asn = int(m.group(1)) if m else None
        rid_m = re.search(r"set interfaces lo0 unit 0 family inet address (\S+)/", config)
        return asn, rid_m.group(1) if rid_m else None
    m = re.search(r"(?:^|\n)(?:router )?bgp (\d+)", config, re.I)
    asn = int(m.group(1)) if m else None
    rid_m = re.search(r"(?:bgp router-id|router-id)\s+(\d+\.\d+\.\d+\.\d+)", config, re.I)
    return asn, rid_m.group(1) if rid_m else None


def _parse_h3c_services(config: str) -> list[L2Service]:
    services: dict[str, L2Service] = {}
    for m in re.finditer(
        r"vsi\s+(\S+).*?vxlan\s+(\d+).*?"
        r"route-distinguisher\s+(\S+).*?"
        r"vpn-target\s+(\S+)\s+import-extcommunity",
        config,
        re.DOTALL | re.I,
    ):
        name = m.group(1)
        svc = services.setdefault(name, L2Service(name=name))
        svc.vni = int(m.group(2))
        svc.rd = m.group(3)
        svc.rt = m.group(4)

    # Map AC interfaces via xconnect vsi
    for m in re.finditer(
        r"^interface\s+(\S+)\s*$(.+?)(?=^interface\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = m.group(1)
        block = m.group(2)
        vsi_m = re.search(r"xconnect vsi\s+(\S+)", block, re.I)
        if not vsi_m:
            continue
        vsi_name = vsi_m.group(1)
        svc = services.setdefault(vsi_name, L2Service(name=vsi_name))
        svc.interfaces.append(iface)
        for svid_m in re.finditer(r"encapsulation s-vid\s+(\d+)", block, re.I):
            svc.vlans.append(int(svid_m.group(1)))
    return list(services.values())


def _parse_huawei_services(config: str) -> list[L2Service]:
    services: dict[str, L2Service] = {}
    for m in re.finditer(
        r"bridge-domain\s+(\d+).*?vxlan vni\s+(\d+)",
        config,
        re.DOTALL | re.I,
    ):
        bd = m.group(1)
        svc = services.setdefault(f"bd_{bd}", L2Service(name=f"bd_{bd}"))
        svc.vni = int(m.group(2))
    for m in re.finditer(
        r"^interface\s+(\S+)\s*$(.+?)(?=^interface\s|\Z|^#|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = m.group(1)
        block = m.group(2)
        bd_m = re.search(r"bridge-domain\s+(\d+)", block, re.I)
        if not bd_m:
            continue
        bd = bd_m.group(1)
        svc = services.setdefault(f"bd_{bd}", L2Service(name=f"bd_{bd}"))
        svc.interfaces.append(iface)
        vid_m = re.search(r"encapsulation dot1q vid\s+(\d+)", block, re.I)
        if vid_m:
            svc.vlans.append(int(vid_m.group(1)))
    return list(services.values())


def _parse_cisco_services(config: str) -> list[L2Service]:
    services: dict[int, L2Service] = {}
    for m in re.finditer(
        r"evi\s+(\d+).*?"
        r"rd\s+(\S+).*?"
        r"route-target import\s+(\S+)",
        config,
        re.DOTALL | re.I,
    ):
        evi = int(m.group(1))
        svc = services.setdefault(evi, L2Service(name=f"evi_{evi}", vni=evi))
        svc.rd = m.group(2)
        svc.rt = m.group(3)
    for m in re.finditer(
        r"bridge-domain\s+(\S+).*?evi\s+(\d+).*?"
        r"interface\s+(\S+)",
        config,
        re.DOTALL | re.I,
    ):
        evi = int(m.group(2))
        svc = services.setdefault(evi, L2Service(name=f"evi_{evi}", vni=evi))
        iface = m.group(3)
        if iface not in svc.interfaces:
            svc.interfaces.append(iface)
    # dot1q on l2transport
    for m in re.finditer(
        r"^interface\s+(\S+)\s*$(.+?)(?=^interface\s|\Z|^!|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        block = m.group(2)
        if not re.search(r"\bl2transport\b", block, re.I):
            continue
        for vid_m in re.finditer(r"encapsulation dot1q\s+(\d+)", block, re.I):
            # attach vlan to first evi service or orphan list handled via vlan_ids
            pass
    return list(services.values())


def _parse_juniper_services(config: str) -> list[L2Service]:
    services: dict[str, L2Service] = {}
    for m in re.finditer(
        r"set routing-instances (\S+) instance-type evpn\n"
        r"(?:set routing-instances \1 .*\n)*",
        config,
    ):
        name = m.group(1)
        block = m.group(0)
        svc = services.setdefault(name, L2Service(name=name))
        rd_m = re.search(rf"set routing-instances {re.escape(name)} route-distinguisher (\S+)", block)
        rt_m = re.search(rf"set routing-instances {re.escape(name)} vrf-target target:(\S+)", block)
        vni_m = re.search(r"extended-vni-list\s+(\d+)", block)
        if rd_m:
            svc.rd = rd_m.group(1)
        if rt_m:
            svc.rt = rt_m.group(1)
        if vni_m:
            svc.vni = int(vni_m.group(1))
    return list(services.values())


def _count_interfaces(config: str, vendor: Vendor) -> int:
    if vendor == Vendor.JUNIPER:
        return len(re.findall(r"^set interfaces \S+", config, re.M))
    return len(re.findall(r"^interface\s+\S+", config, re.M))


def _collect_vlan_ids(config: str, vendor: Vendor) -> list[int]:
    ids: set[int] = set()
    for m in re.finditer(
        r"(?:s-vid|dot1q|vlan-id|vid)\s+(\d+)", config, re.I
    ):
        ids.add(int(m.group(1)))
    return sorted(ids)


def parse_inventory(config: str, vendor: Vendor) -> LearnedInventory:
    """Extract structured inventory from raw running-config text."""
    inv = LearnedInventory()
    inv.loopback_ip = _parse_loopback(config, vendor)
    inv.bgp_asn, inv.bgp_router_id = _parse_bgp_asn(config, vendor)
    inv.interface_count = _count_interfaces(config, vendor)
    inv.vlan_ids = _collect_vlan_ids(config, vendor)

    if vendor == Vendor.H3C:
        inv.l2_services = _parse_h3c_services(config)
    elif vendor == Vendor.HUAWEI:
        inv.l2_services = _parse_huawei_services(config)
    elif vendor == Vendor.CISCO:
        inv.l2_services = _parse_cisco_services(config)
    elif vendor == Vendor.JUNIPER:
        inv.l2_services = _parse_juniper_services(config)
    else:
        inv.l2_services = _parse_h3c_services(config) or _parse_cisco_services(config)

    for svc in inv.l2_services:
        inv.vlan_ids.extend(svc.vlans)
    inv.vlan_ids = sorted(set(inv.vlan_ids))
    return inv
