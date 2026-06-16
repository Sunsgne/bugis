"""Fetch live running-config from devices (NETCONF / CLI).

In dry-run mode returns vendor-realistic simulated configs for demo devices so
the learn pipeline can be exercised without live gear.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.drivers import get_driver
from app.models.device import Device
from app.models.enums import Vendor

_PROMPT_LINE = re.compile(r"^<[^>]+>$|^\[[^\]]+\]$|^[<\[].*[>\]]$")
_CONFIG_MARKERS = (
    "interface ",
    "sysname ",
    "hostname ",
    "bgp ",
    "router bgp",
    "l2vpn",
    "vsi ",
    "bridge-domain",
    "set interfaces",
    "set system",
    "return",
    "#",
    "!",
)

# Demo running-config snippets keyed by device name (aligned with seed + port_inventory).
_SIMULATED: dict[str, str] = {
    "BJ-LEAF-01": """\
! H3C Comware7 running-config (learned)
sysname BJ-LEAF-01
#
interface LoopBack0
 ip address 10.1.255.11 255.255.255.255
#
bgp 65001
 router-id 10.1.255.11
 #
 address-family l2vpn evpn
  peer 10.1.255.1 enable
#
l2vpn enable
#
vsi vsi_DEMO-L2-001
 description Demo E-LAN learned from live
 vxlan 10100
 evpn encapsulation vxlan
  route-distinguisher 65001:10100
  vpn-target 65001:10100 import-extcommunity
  vpn-target 65001:10100 export-extcommunity
#
interface GE1/0/1
 port link-mode route
 description UPLINK
#
interface GE1/0/5
 port link-mode bridge
 description legacy customer AC
 service-instance 120
  encapsulation s-vid 120
  xconnect vsi vsi_DEMO-L2-001
#
interface GE1/0/10
 port link-mode bridge
 service-instance 200
  encapsulation s-vid 200
  xconnect vsi vsi_DEMO-L2-001
#
return
""",
    "SH-PE-01": """\
! Cisco IOS-XR running-config (learned)
hostname SH-PE-01
!
interface Loopback0
 ipv4 address 10.2.255.21 255.255.255.255
!
router bgp 65002
 bgp router-id 10.2.255.21
 !
 address-family l2vpn evpn
  neighbor 10.2.255.1
   activate
!
interface GigabitEthernet0/0/0/2
 description legacy manual AC
 l2transport
  encapsulation dot1q 150
!
interface GigabitEthernet0/0/0/3
 description legacy manual AC
 l2transport
  encapsulation dot1q 280
!
l2vpn
 bridge group BG_LEARNED-001
  bridge-domain BD_LEARNED-001
   interface GigabitEthernet0/0/0/2
   evi 10200
!
evpn
 evi 10200
  bgp
   rd 65002:10200
   route-target import 65002:10200
   route-target export 65002:10200
  advertise-mac
!
""",
    "SH-LEAF-01": """\
# Huawei VRP running-config (learned)
sysname SH-LEAF-01
#
interface LoopBack0
 ip address 10.2.255.11 255.255.255.255
#
bgp 65002
 router-id 10.2.255.11
 #
 l2vpn-family evpn
  peer 10.2.255.1 enable
#
bridge-domain 10300
 vxlan vni 10300
 evpn binding vpn-instance EVPN_10300
#
interface GE1/0/1
 description UPLINK
#
interface GE1/0/8.100
 encapsulation dot1q vid 100
 bridge-domain 10300
#
return
""",
    "GZ-PE-01": """\
set system host-name GZ-PE-01
set interfaces lo0 unit 0 family inet address 10.3.255.21/32
set routing-options autonomous-system 65003
set routing-instances EVPN-10400 instance-type evpn
set routing-instances EVPN-10400 route-distinguisher 65003:10400
set routing-instances EVPN-10400 vrf-target target:65003:10400
set routing-instances EVPN-10400 protocols evpn extended-vni-list 10400
set interfaces ge-0/0/1 unit 0 vlan-id 300
set interfaces ge-0/0/1 unit 0 family bridge interface-mode access
set interfaces ge-0/0/1 unit 0 family bridge vlan-id 300
""",
}

_VENDOR_FALLBACK: dict[str, str] = {
    "h3c": """\
! Generic H3C learned config
sysname DEVICE
interface LoopBack0
 ip address 10.255.255.1 255.255.255.255
bgp 65000
 router-id 10.255.255.1
l2vpn enable
vsi vsi_IMPORTED
 vxlan 10001
 evpn encapsulation vxlan
  route-distinguisher 65000:10001
  vpn-target 65000:10001 import-extcommunity
  vpn-target 65000:10001 export-extcommunity
interface GE1/0/1
 port link-mode bridge
 service-instance 100
  encapsulation s-vid 100
  xconnect vsi vsi_IMPORTED
return
""",
    "huawei": """\
sysname DEVICE
interface LoopBack0
 ip address 10.255.255.1 255.255.255.255
bgp 65000
 router-id 10.255.255.1
bridge-domain 10001
 vxlan vni 10001
interface GE1/0/1.100
 encapsulation dot1q vid 100
 bridge-domain 10001
return
""",
    "cisco": """\
hostname DEVICE
interface Loopback0
 ipv4 address 10.255.255.1 255.255.255.255
router bgp 65000
 bgp router-id 10.255.255.1
interface GigabitEthernet0/0/0/1
 l2transport
  encapsulation dot1q 100
l2vpn
 bridge group BG_IMPORTED
  bridge-domain BD_IMPORTED
   evi 10001
evpn
 evi 10001
  bgp
   rd 65000:10001
   route-target import 65000:10001
   route-target export 65000:10001
""",
    "juniper": """\
set interfaces lo0 unit 0 family inet address 10.255.255.1/32
set routing-options autonomous-system 65000
set routing-instances RI-EVPN instance-type evpn
set routing-instances RI-EVPN route-distinguisher 65000:10001
set routing-instances RI-EVPN vrf-target target:65000:10001
set interfaces ge-0/0/0 unit 0 vlan-id 100
""",
}


def simulated_config(device: Device) -> str:
    """Return dry-run simulated running-config for a device."""
    if device.name in _SIMULATED:
        return _SIMULATED[device.name]
    vendor_key = device.vendor.value
    body = _VENDOR_FALLBACK.get(vendor_key, _VENDOR_FALLBACK["h3c"])
    return body.replace("DEVICE", device.name)


def looks_like_running_config(content: str, vendor: Vendor | None = None) -> bool:
    """Reject empty output, CLI prompt echoes, and other non-config noise."""
    text = (content or "").strip()
    if not text:
        return False

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 8:
        return False

    meaningful = [ln for ln in lines if not _PROMPT_LINE.match(ln)]
    if len(meaningful) < 8:
        return False

    lowered = text.lower()
    if not any(marker in lowered for marker in _CONFIG_MARKERS):
        return False

    if vendor in (Vendor.H3C, Vendor.HUAWEI) and "interface" not in lowered:
        return False

    return True


def _fetch_once(device: Device) -> tuple[bool, str, str | None]:
    """Single fetch attempt via device.active_mgmt_ip."""
    driver = get_driver(device.vendor)
    result = driver.fetch_config(device, dry_run=settings.dry_run)
    if not result.success:
        return False, "", result.output or "fetch failed"
    if settings.dry_run:
        return True, result.config, None
    if looks_like_running_config(result.config, device.vendor):
        return True, result.config, None

    fallback = driver.fetch_config(device, dry_run=False, allow_transport_fallback=True)
    if fallback.success and looks_like_running_config(fallback.config, device.vendor):
        return True, fallback.config, None

    line_count = len((result.config or "").splitlines())
    return (
        False,
        "",
        (
            f"running-config looks invalid ({line_count} line(s)); "
            "check SSH paging/timeout or NETCONF access"
        ),
    )


def _ordered_mgmt_candidates(device: Device) -> list[dict[str, str]]:
    from app.services import device_management

    candidates = device_management.mgmt_ip_candidates(device)
    active = device.mgmt_ip_active
    if not active:
        return candidates
    ordered: list[dict[str, str]] = []
    rest: list[dict[str, str]] = []
    for cand in candidates:
        if cand["ip"] == active:
            ordered.append(cand)
        else:
            rest.append(cand)
    seen = {c["ip"] for c in ordered}
    for cand in rest:
        if cand["ip"] not in seen:
            ordered.append(cand)
            seen.add(cand["ip"])
    return ordered or candidates


def fetch_running_config(
    device: Device,
    db: Session | None = None,
) -> tuple[bool, str, str | None]:
    """Pull running-config; refresh reachability and failover across mgmt IPs."""
    from app.services import device_management

    if db is not None:
        device_management.probe_reachability(db, device, persist=True)

    if settings.dry_run:
        return _fetch_once(device)

    last_err: str | None = None
    for cand in _ordered_mgmt_candidates(device):
        prev_active = device.mgmt_ip_active
        prev_role = device.mgmt_ip_active_role
        device.mgmt_ip_active = cand["ip"]
        device.mgmt_ip_active_role = cand["role"]
        ok, content, err = _fetch_once(device)
        if ok:
            if db is not None:
                device_management.persist_active_endpoint(
                    device,
                    cand["ip"],
                    cand["role"],
                    method="fetch",
                )
            return True, content, None
        last_err = err
        device.mgmt_ip_active = prev_active
        device.mgmt_ip_active_role = prev_role

    return False, "", last_err or "fetch failed on all management IPs"
