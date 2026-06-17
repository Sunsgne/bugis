"""Tests for the vendor-aware config sanitizer (display-style -> paste-safe)."""
from __future__ import annotations

from app.drivers.config_text import to_command_list, to_command_text
from app.models.enums import Vendor

HUAWEI_DISPLAY = """\
#
# Huawei VRP (Datacom) - EVPN VXLAN L2VPN  circuit=CIR-5AF450 vni=30002
# device=cs-1.eqty8-2f-000010-row1-108-u14.tyo1 ac=dot1q s-vid=1234
#
# QoS CAR via classifier/behavior/traffic-policy (VRP); cir unit = kbps
traffic classifier tc-CIR-5AF450 type or
 if-match any
#
traffic behavior tb-CIR-5AF450
 car cir 102400 cbs 6400000 green pass red discard yellow pass
#
bridge-domain 30002
 mtu 9000
 vxlan vni 30002
#
interface 10GE1/0/11.1234 mode l2
 description CUST_4_CIR-5AF450
 encapsulation dot1q vid 1234
 bridge-domain 30002
#
return
"""

H3C_DISPLAY = """\
#
# H3C Comware7 - EVPN VXLAN L2VPN (E-LAN)  circuit=CIR-1 vni=10100
#
l2vpn enable
#
vsi vsi_CIR-1
 vxlan 10100
#
interface GE1/0/5
 port link-mode bridge
#
return
"""

FRR_DISPLAY = """\
! FRRouting - EVPN-VXLAN L2 (E-LAN)  circuit=CIR-1 vni=10100
! device=leaf1 lo=10.0.0.1
configure terminal
!
vni 10100
end
"""

JUNOS_DISPLAY = """\
## Juniper Junos - EVPN-MPLS L2  circuit=CIR-1 evi=10100
## device=pe1 lo0=10.0.0.1
set interfaces ge-0/0/1 unit 0 vlan-id 100
set routing-instances RI instance-type evpn
"""


def test_huawei_strips_banners_separators_and_return():
    cmds = to_command_list(Vendor.HUAWEI, HUAWEI_DISPLAY)
    # No comment/banner lines, no bare separators, no trailing return.
    assert all(not c.lstrip().startswith("#") for c in cmds)
    assert "return" not in [c.strip().lower() for c in cmds]
    assert "" not in cmds  # no blank lines
    # Real config commands preserved, including indented sub-view lines.
    assert "traffic classifier tc-CIR-5AF450 type or" in cmds
    assert " if-match any" in cmds
    assert "bridge-domain 30002" in cmds
    assert " encapsulation dot1q vid 1234" in cmds
    assert "interface 10GE1/0/11.1234 mode l2" in cmds


def test_h3c_strips_banner_and_return_keeps_commands():
    cmds = to_command_list(Vendor.H3C, H3C_DISPLAY)
    assert "l2vpn enable" in cmds
    assert "vsi vsi_CIR-1" in cmds
    assert "interface GE1/0/5" in cmds
    assert all(not c.lstrip().startswith("#") for c in cmds)
    assert "return" not in [c.strip().lower() for c in cmds]


def test_hash_vendor_keeps_quit_but_drops_return():
    # 'return' (jump to user view) is dropped; 'quit' (pop one view) is kept so
    # teardown templates can return to system-view before system-scoped undo.
    cfg = "interface GE1/0/5\n undo service-instance 1\n quit\nundo vsi v1\nreturn\n"
    cmds = to_command_list(Vendor.H3C, cfg)
    assert "quit" in [c.strip().lower() for c in cmds]
    assert "return" not in [c.strip().lower() for c in cmds]
    # quit must come before the system-view undo that follows the interface block
    assert cmds.index(" quit") < cmds.index("undo vsi v1")


def test_frr_strips_bang_comments_keeps_config_terminal():
    cmds = to_command_list(Vendor.FRR, FRR_DISPLAY)
    assert "configure terminal" in cmds
    assert "end" in cmds
    assert "vni 10100" in cmds
    assert all(not c.lstrip().startswith("!") for c in cmds)


def test_junos_strips_annotation_keeps_set():
    cmds = to_command_list(Vendor.JUNIPER, JUNOS_DISPLAY)
    assert "set interfaces ge-0/0/1 unit 0 vlan-id 100" in cmds
    assert "set routing-instances RI instance-type evpn" in cmds
    assert all(not c.lstrip().startswith("#") for c in cmds)


def test_empty_and_none_inputs():
    assert to_command_list(Vendor.HUAWEI, "") == []
    assert to_command_list(Vendor.HUAWEI, None) == []
    assert to_command_text(Vendor.HUAWEI, "#\nreturn\n") == ""


def test_to_command_text_joins_with_newlines():
    text = to_command_text(Vendor.H3C, H3C_DISPLAY)
    assert "\n" in text
    assert text.splitlines() == to_command_list(Vendor.H3C, H3C_DISPLAY)
