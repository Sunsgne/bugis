"""Southbound management interface resolution tests."""
from __future__ import annotations

from app.models.device import Device
from app.models.enums import ManagementTransport, Vendor
from app.services import device_management


def test_effective_transport_respects_device_override():
    device = Device(
        name="t",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        management_transport=ManagementTransport.SSH,
    )
    assert device_management.effective_transport(device) == "ssh"


def test_effective_transport_auto_uses_vendor_default():
    device = Device(
        name="t",
        vendor=Vendor.ARISTA,
        mgmt_ip="10.0.0.1",
        management_transport=ManagementTransport.AUTO,
    )
    assert device_management.effective_transport(device) == "cli"


def test_probe_port_for_ssh():
    device = Device(name="t", vendor=Vendor.FRR, mgmt_ip="10.0.0.1", ssh_port=2222)
    assert device_management.probe_port(device, "ssh") == 2222
