"""Fabric capacity should count physical ports only."""
from __future__ import annotations

from app.models.device import DeviceInterface
from app.services.capacity_service import is_physical_capacity_interface, _physical_capacity_mbps


def test_excludes_vlan_and_subif_from_capacity():
    ifaces = [
        DeviceInterface(name="10GE1/0/1", speed_mbps=10000),
        DeviceInterface(name="10GE1/0/2", speed_mbps=10000),
        DeviceInterface(name="10GE1/0/2.1050", speed_mbps=10000),
        DeviceInterface(name="Vlanif100", speed_mbps=10000),
        DeviceInterface(name="Vlan-interface100", speed_mbps=10000),
        DeviceInterface(name="Bridge-Aggregation1", speed_mbps=40000),
        DeviceInterface(name="LoopBack0", speed_mbps=0),
    ]
    assert _physical_capacity_mbps(ifaces) == 20000
    assert is_physical_capacity_interface("10GE1/0/1")
    assert not is_physical_capacity_interface("10GE1/0/2.1050")
    assert not is_physical_capacity_interface("Vlanif200")
    assert not is_physical_capacity_interface("Bridge-Aggregation1")
