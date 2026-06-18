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
class AccessBinding:
    """Per-AC chain: interface / encapsulation → overlay service → VNI."""

    interface: str
    access_mode: str = "dot1q"
    s_vid: int | None = None
    c_vid: int | None = None
    service_instance: int | None = None
    vsi_name: str | None = None
    bridge_domain: str | None = None
    vni: int | None = None
    rd: str | None = None
    rt: str | None = None
    description: str | None = None

    def as_dict(self) -> dict:
        return {
            "interface": self.interface,
            "access_mode": self.access_mode,
            "s_vid": self.s_vid,
            "c_vid": self.c_vid,
            "service_instance": self.service_instance,
            "vsi_name": self.vsi_name,
            "bridge_domain": self.bridge_domain,
            "vni": self.vni,
            "rd": self.rd,
            "rt": self.rt,
            "description": self.description,
        }


@dataclass
class LearnedInventory:
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    bgp_router_id: str | None = None
    l2_services: list[L2Service] = field(default_factory=list)
    access_bindings: list[AccessBinding] = field(default_factory=list)
    interface_count: int = 0
    vlan_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "loopback_ip": self.loopback_ip,
            "bgp_asn": self.bgp_asn,
            "bgp_router_id": self.bgp_router_id,
            "l2_services": [s.as_dict() for s in self.l2_services],
            "access_bindings": [b.as_dict() for b in self.access_bindings],
            "interface_count": self.interface_count,
            "vlan_ids": sorted(set(self.vlan_ids)),
            "service_count": len(self.l2_services),
            "binding_count": len(self.access_bindings),
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


def _build_h3c_vsi_registry(config: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(
        r"^vsi\s+(\S+)\s*$(.+?)(?=^vsi\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ):
        name = m.group(1)
        body = m.group(2)
        vni_m = re.search(r"vxlan\s+(\d+)", body, re.I)
        rd_m = re.search(r"route-distinguisher\s+(\S+)", body, re.I)
        rt_m = re.search(r"vpn-target\s+(\S+)\s+import-extcommunity", body, re.I)
        out[name] = {
            "vni": int(vni_m.group(1)) if vni_m else None,
            "rd": rd_m.group(1) if rd_m else None,
            "rt": rt_m.group(1) if rt_m else None,
        }
    return out


def _build_huawei_bd_registry(config: str) -> dict[str, dict]:
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
        out[bd] = {
            "vni": int(vni_m.group(1)) if vni_m else None,
            "rd": rd_m.group(1) if rd_m else None,
            "rt": rt_m.group(1) if rt_m else None,
        }
    return out


def _parse_h3c_access_bindings(config: str, vsi_reg: dict[str, dict]) -> list[AccessBinding]:
    bindings: list[AccessBinding] = []
    for m in re.finditer(
        r"^interface\s+(\S+)\s*$(.+?)(?=^interface\s|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = m.group(1)
        block = m.group(2)
        iface_desc_m = re.search(r"^\s*description\s+(.+)$", block, re.MULTILINE | re.IGNORECASE)
        iface_desc = iface_desc_m.group(1).strip() if iface_desc_m else None

        for si_m in re.finditer(
            r"service-instance\s+(\d+)\s*\n(.*?)(?=^\s*service-instance\s|\Z)",
            block,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        ):
            si_id = int(si_m.group(1))
            si_body = si_m.group(2)
            desc_m = re.search(r"^\s*description\s+(.+)$", si_body, re.MULTILINE | re.IGNORECASE)
            vsi_m = re.search(r"xconnect\s+vsi\s+(\S+)", si_body, re.I)
            vsi_name = vsi_m.group(1) if vsi_m else None
            meta = vsi_reg.get(vsi_name or "", {})

            if re.search(r"encapsulation\s+untagged", si_body, re.I):
                bindings.append(
                    AccessBinding(
                        interface=iface,
                        access_mode="access",
                        service_instance=si_id,
                        vsi_name=vsi_name,
                        vni=meta.get("vni"),
                        rd=meta.get("rd"),
                        rt=meta.get("rt"),
                        description=(desc_m.group(1).strip() if desc_m else None) or iface_desc,
                    )
                )
                continue

            qinq_m = re.search(
                r"encapsulation\s+s-vid\s+(\d+)\s+c-vid\s+(\d+)", si_body, re.I
            )
            if qinq_m:
                bindings.append(
                    AccessBinding(
                        interface=iface,
                        access_mode="qinq",
                        s_vid=int(qinq_m.group(1)),
                        c_vid=int(qinq_m.group(2)),
                        service_instance=si_id,
                        vsi_name=vsi_name,
                        vni=meta.get("vni"),
                        rd=meta.get("rd"),
                        rt=meta.get("rt"),
                        description=(desc_m.group(1).strip() if desc_m else None) or iface_desc,
                    )
                )
                continue

            dot1q_m = re.search(r"encapsulation\s+s-vid\s+(\d+)", si_body, re.I)
            if dot1q_m:
                bindings.append(
                    AccessBinding(
                        interface=iface,
                        access_mode="dot1q",
                        s_vid=int(dot1q_m.group(1)),
                        service_instance=si_id,
                        vsi_name=vsi_name,
                        vni=meta.get("vni"),
                        rd=meta.get("rd"),
                        rt=meta.get("rt"),
                        description=(desc_m.group(1).strip() if desc_m else None) or iface_desc,
                    )
                )
    return bindings


def _parse_huawei_access_bindings(config: str, bd_reg: dict[str, dict]) -> list[AccessBinding]:
    bindings: list[AccessBinding] = []
    for m in re.finditer(
        r"^interface\s+(\S+)(?:\s+mode\s+\S+)?\s*$(.+?)(?=^interface\s|\Z|^#|\Z)",
        config,
        re.MULTILINE | re.DOTALL,
    ):
        iface = m.group(1)
        block = m.group(2)
        bd_m = re.search(r"bridge-domain\s+(\S+)", block, re.I)
        if not bd_m:
            continue
        bd = bd_m.group(1)
        meta = bd_reg.get(bd, {})
        desc_m = re.search(r"^\s*description\s+(.+)$", block, re.MULTILINE | re.IGNORECASE)
        description = desc_m.group(1).strip() if desc_m else None

        if re.search(r"encapsulation\s+untag", block, re.I):
            bindings.append(
                AccessBinding(
                    interface=iface,
                    access_mode="access",
                    bridge_domain=bd,
                    vni=meta.get("vni"),
                    rd=meta.get("rd"),
                    rt=meta.get("rt"),
                    description=description,
                )
            )
            continue

        qinq_matches = list(
            re.finditer(
                r"encapsulation\s+qinq\s+vid\s+(\d+)\s+ce-vid\s+(\d+)", block, re.I
            )
        )
        if qinq_matches:
            for qinq_m in qinq_matches:
                bindings.append(
                    AccessBinding(
                        interface=iface,
                        access_mode="qinq",
                        s_vid=int(qinq_m.group(1)),
                        c_vid=int(qinq_m.group(2)),
                        bridge_domain=bd,
                        vni=meta.get("vni"),
                        rd=meta.get("rd"),
                        rt=meta.get("rt"),
                        description=description,
                    )
                )
            continue

        dot1q_m = re.search(r"encapsulation\s+dot1q\s+vid\s+(\d+)", block, re.I)
        if dot1q_m:
            bindings.append(
                AccessBinding(
                    interface=iface,
                    access_mode="dot1q",
                    s_vid=int(dot1q_m.group(1)),
                    bridge_domain=bd,
                    vni=meta.get("vni"),
                    rd=meta.get("rd"),
                    rt=meta.get("rt"),
                    description=description,
                )
            )
    return bindings


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
        vsi_reg = _build_h3c_vsi_registry(config)
        inv.l2_services = _parse_h3c_services(config)
        inv.access_bindings = _parse_h3c_access_bindings(config, vsi_reg)
    elif vendor == Vendor.HUAWEI:
        bd_reg = _build_huawei_bd_registry(config)
        inv.l2_services = _parse_huawei_services(config)
        inv.access_bindings = _parse_huawei_access_bindings(config, bd_reg)
    elif vendor == Vendor.CISCO:
        inv.l2_services = _parse_cisco_services(config)
    elif vendor == Vendor.JUNIPER:
        inv.l2_services = _parse_juniper_services(config)
    else:
        inv.l2_services = _parse_h3c_services(config) or _parse_cisco_services(config)
        if inv.l2_services:
            vsi_reg = _build_h3c_vsi_registry(config)
            inv.access_bindings = _parse_h3c_access_bindings(config, vsi_reg)

    for svc in inv.l2_services:
        inv.vlan_ids.extend(svc.vlans)
    for binding in inv.access_bindings:
        if binding.s_vid is not None:
            inv.vlan_ids.append(binding.s_vid)
    inv.vlan_ids = sorted(set(inv.vlan_ids))
    return inv
