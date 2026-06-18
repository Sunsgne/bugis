"""Unit tests for port S-VID inventory (pure parsing, no DB)."""
from __future__ import annotations

from app.models.enums import Vendor
from app.services import port_inventory


def test_parse_h3c_svid_details():
    config = """
vsi cus-demo-001
 description Customer Demo Link
 vxlan 10148
 evpn encapsulation vxlan
  route-distinguisher 10.1.1.1:10148
traffic classifier tc-demo operator and
 if-match any
#
traffic behavior tb-demo
 car cir 204800 cbs 12800000 ebs 0 green pass red discard yellow pass
#
qos policy qp-demo
 classifier tc-demo behavior tb-demo
#
interface GE1/0/50
 description ISP: uplink port
 service-instance 2501
  description AC for customer A
  encapsulation s-vid 2501
  qos apply policy qp-demo inbound
  qos apply policy qp-demo outbound
  xconnect vsi cus-demo-001
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.H3C)
    entry = parsed["GE1/0/50"][0]
    assert entry.s_vid == 2501
    assert entry.vsi_name == "cus-demo-001"
    assert entry.rate_limit_mbps == 200
    assert "customer A" in (entry.description or "")

    vsi_map = port_inventory._parse_h3c_vsi_map(config)
    assert vsi_map["cus-demo-001"]["vni"] == 10148
    port_inventory._enrich_svid_entry(entry, catalog=port_inventory._CircuitCatalog({}, {}, {}), vsi_map=vsi_map)
    assert entry.vni == 10148


def test_parse_h3c_svid():
    config = """
interface GE1/0/1
 service-instance 100
  encapsulation s-vid 100
  xconnect vsi vsi_test
!
interface GE1/0/2
 service-instance 1
  encapsulation untagged
!
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.H3C)
    assert "GE1/0/1" in parsed
    assert parsed["GE1/0/1"][0].s_vid == 100
    assert parsed["GE1/0/2"][0].access_mode == "access"


def test_parse_cisco_dot1q():
    config = """
interface GigabitEthernet0/0/0/2
 l2transport
  encapsulation dot1q 150
!
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.CISCO)
    assert parsed["GigabitEthernet0/0/0/2"][0].s_vid == 150


def test_find_conflicts_duplicate():
    usage = port_inventory.PortUsage(
        interface_name="GE1/0/1",
        entries=[
            port_inventory.SvidEntry(s_vid=100, source="platform", circuit_code="CIR-A"),
            port_inventory.SvidEntry(s_vid=100, source="legacy"),
        ],
    )
    conflicts = port_inventory.find_conflicts({"GE1/0/1": usage})
    assert conflicts


def test_remap_h3c_snmp_interface_names():
    config = """
interface GE1/0/25
 service-instance 400
  encapsulation s-vid 400
!
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.H3C)
    remapped = port_inventory._remap_config_usage(
        {k: port_inventory.PortUsage(interface_name=k, entries=v) for k, v in parsed.items()},
        {"HundredGigE1/0/25", "HundredGigE1/0/26"},
    )
    assert "HundredGigE1/0/25" in remapped
    assert remapped["HundredGigE1/0/25"].entries[0].s_vid == 400


def test_remap_platform_usage_to_snmp_name():
    alias_map = port_inventory._build_alias_map({"Twenty-FiveGigE1/0/1", "Twenty-FiveGigE1/0/2"})
    plat = {
        "GE1/0/1": port_inventory.PortUsage(
            interface_name="GE1/0/1",
            entries=[
                port_inventory.SvidEntry(
                    s_vid=101,
                    source="platform",
                    circuit_code="CIR-DEMO",
                )
            ],
        )
    }
    remapped = port_inventory._remap_usage_map(plat, alias_map)
    assert "Twenty-FiveGigE1/0/1" in remapped
    assert "GE1/0/1" not in remapped
    assert remapped["Twenty-FiveGigE1/0/1"].entries[0].s_vid == 101


def test_resolve_iface_name_aliases():
    alias_map = port_inventory._build_alias_map({"Twenty-FiveGigE1/0/1"})
    assert (
        port_inventory._resolve_iface_name("GE1/0/1", alias_map)
        == "Twenty-FiveGigE1/0/1"
    )
    assert (
        port_inventory._resolve_iface_name("GigabitEthernet1/0/1", alias_map)
        == "Twenty-FiveGigE1/0/1"
    )


def test_parse_description_svid():
    entries = port_inventory._parse_description_entries("cust-ac vlan=120 bw(1Gbps)")
    assert entries[0].s_vid == 120
    assert entries[0].source == "device"


def test_parse_h3c_qos_apply_policy_rate_limit():
    config = """
traffic classifier tc-rl operator and
 if-match any
#
traffic behavior tb-rl
 car cir 51200 cbs 3200000 ebs 0 green pass red discard yellow pass
#
qos policy qp-rl
 classifier tc-rl behavior tb-rl
#
interface GE1/0/1
 service-instance 100
  encapsulation s-vid 100
  qos apply policy qp-rl inbound
  xconnect vsi vsi_test
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.H3C)
    assert parsed["GE1/0/1"][0].rate_limit_mbps == 50


def test_parse_huawei_traffic_policy_rate_limit():
    config = """
traffic classifier tc-rl operator or
 if-match any
#
traffic behavior tb-rl
 car cir 614400 cbs 38400000 green pass red discard yellow pass
#
traffic policy tp-rl
 classifier tc-rl behavior tb-rl
#
bridge-domain 30100
 vxlan vni 30100
 evpn
  route-distinguisher 65002:30100
  vpn-target 65002:30100 import-extcommunity
interface GE1/0/1.100 mode l2
 encapsulation dot1q vid 100
 traffic-policy tp-rl inbound
 traffic-policy tp-rl outbound
 bridge-domain 30100
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.HUAWEI)
    entry = parsed["GE1/0/1.100"][0]
    assert entry.s_vid == 100
    assert entry.bridge_domain == "30100"
    assert entry.rate_limit_mbps == 600
    bd_map = port_inventory._parse_huawei_bd_map(config)
    assert bd_map["30100"]["vni"] == 30100
    port_inventory._enrich_svid_entry(
        entry,
        catalog=port_inventory._CircuitCatalog({}, {}, {}),
        bd_map=bd_map,
    )
    assert entry.vni == 30100


def test_huawei_subinterface_helpers():
    assert port_inventory.is_huawei_subinterface("10GE1/0/2.1050")
    assert port_inventory.parse_huawei_subinterface("10GE1/0/2.1050") == ("10GE1/0/2", 1050)
    assert port_inventory.huawei_physical_port("10GE1/0/2.1050") == "10GE1/0/2"
    assert not port_inventory.is_huawei_subinterface("10GE1/0/2")


def test_list_physical_interfaces_from_config_huawei():
    config = """
interface 10GE1/0/2.1050 mode l2
 encapsulation dot1q vid 1050
#
interface 10GE1/0/3
 description uplink
#
interface LoopBack0
 ip address 10.1.1.1 255.255.255.255
#
interface Vlanif201
 ip address 10.2.2.1 255.255.255.0
"""
    names = port_inventory.list_physical_interfaces_from_config(config, Vendor.HUAWEI)
    assert "10GE1/0/2" in names
    assert "10GE1/0/3" in names
    assert "10GE1/0/2.1050" not in names
    assert "LoopBack0" not in names
    assert "Vlanif201" not in names


def test_list_vlan_interfaces_from_config():
    config = """
interface Vlanif4010
 description DCI peer bw(10000M)
 ip address 10.10.10.1 255.255.255.252
#
interface Vlan-interface4001
 description H3C DCI
 ip address 10.20.20.1 255.255.255.252
#
interface 10GE1/0/3
 description uplink
"""
    vlans = port_inventory.list_vlan_interfaces_from_config(config, Vendor.HUAWEI)
    by_name = {row["name"]: row for row in vlans}
    assert "Vlanif4010" in by_name
    assert by_name["Vlanif4010"]["description"] == "DCI peer bw(10000M)"
    assert "Vlan-interface4001" in by_name
    assert by_name["Vlan-interface4001"]["description"] == "H3C DCI"


def test_rollup_huawei_subif_usage_to_physical_port():
    config = """
interface 10GE1/0/2.1050 mode l2
 encapsulation dot1q vid 1050
 traffic-policy tp-rl inbound
#
interface 10GE1/0/2.1064 mode l2
 encapsulation dot1q vid 1064
#
interface 10GE1/0/3.1125 mode l2
 encapsulation dot1q vid 1125
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.HUAWEI)
    port_map = {
        iface: port_inventory.PortUsage(interface_name=iface, entries=entries)
        for iface, entries in parsed.items()
    }
    rolled = port_inventory._rollup_huawei_subif_usage(port_map)
    assert "10GE1/0/2.1050" not in rolled
    assert rolled["10GE1/0/2"].entries[0].s_vid == 1050
    assert rolled["10GE1/0/2"].entries[1].s_vid == 1064
    assert rolled["10GE1/0/3"].entries[0].s_vid == 1125


def test_remap_huawei_subif_config_to_snmp_physical():
    config = """
interface 10GE1/0/2.1050 mode l2
 encapsulation dot1q vid 1050
"""
    parsed = port_inventory._parse_interface_blocks(config, Vendor.HUAWEI)
    port_map = {
        iface: port_inventory.PortUsage(interface_name=iface, entries=entries)
        for iface, entries in parsed.items()
    }
    rolled = port_inventory._rollup_huawei_subif_usage(port_map)
    remapped = port_inventory._remap_config_usage(
        rolled,
        {"10GE1/0/2", "10GE1/0/3"},
    )
    assert "10GE1/0/2" in remapped
    assert remapped["10GE1/0/2"].entries[0].s_vid == 1050


def test_resolve_huawei_subif_to_parent_snmp_name():
    alias_map = port_inventory._build_alias_map({"10GE1/0/2", "10GE1/0/3"})
    assert (
        port_inventory._resolve_iface_name("10GE1/0/2.1050", alias_map)
        == "10GE1/0/2"
    )

