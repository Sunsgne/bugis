"""Dual management IP failover tests."""
from __future__ import annotations

from unittest.mock import patch

from app.models.device import Device
from app.models.enums import Vendor
from app.services import device_management


def test_probe_failover_to_backup_ip():
    device = Device(
        name="edge",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        mgmt_ip_backup="203.0.113.10",
        mgmt_ip_primary_label="管理网",
        mgmt_ip_backup_label="公网",
        ssh_port=22,
        netconf_port=830,
    )
    calls: list[str] = []

    def fake_tcp(host, port, timeout=3.0):
        calls.append(host)
        if host == "10.0.0.1":
            return False, None, "timeout"
        return True, 5.5, None

    with patch("app.services.device_management._tcp_probe", side_effect=fake_tcp):
        result = device_management.probe_reachability(None, device, persist=True)

    assert result["reachable"] is True
    assert result["mgmt_ip_active"] == "203.0.113.10"
    assert result["mgmt_ip_active_role"] == "backup"
    assert result["mgmt_ip_active_label"] == "公网"
    assert device.mgmt_ip_active == "203.0.113.10"
    assert calls[0] == "10.0.0.1"
    assert "203.0.113.10" in calls


def test_effective_mgmt_ip_uses_active():
    device = Device(name="t", vendor=Vendor.H3C, mgmt_ip="10.0.0.1", mgmt_ip_active="203.0.113.5")
    assert device_management.effective_mgmt_ip(device) == "203.0.113.5"
