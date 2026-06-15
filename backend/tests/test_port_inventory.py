"""Unit tests for port S-VID inventory (pure parsing, no DB)."""
from __future__ import annotations

from app.models.enums import Vendor
from app.services import port_inventory


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
