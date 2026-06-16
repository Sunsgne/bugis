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
interface GE1/0/50
 description ISP: uplink port
 service-instance 2501
  description AC for customer A
  encapsulation s-vid 2501
  qos car inbound any cir 200000 cbs 5000000
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
