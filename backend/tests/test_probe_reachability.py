"""Reachability probe tries SSH, NETCONF, then SNMP."""
from __future__ import annotations

from unittest.mock import patch

from app.models.device import Device
from app.models.enums import Vendor
from app.services import device_management


def test_probe_reachability_dry_run():
    device = Device(name="t", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = True
        with patch("app.services.device_management.random.random", return_value=0.5):
            result = device_management.probe_reachability(None, device)
    assert result["reachable"] is True
    assert result["method"] == "dry_run"


def test_probe_reachability_tcp_ssh():
    device = Device(
        name="t",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        ssh_port=22,
        netconf_port=830,
    )
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = False
        with patch(
            "app.services.device_management._tcp_probe",
            side_effect=[(True, 1.2, None)],
        ):
            result = device_management.probe_reachability(None, device)
    assert result["reachable"] is True
    assert result["method"] == "tcp_ssh"


def test_probe_reachability_snmp_fallback():
    device = Device(
        name="t",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        snmp_enabled=True,
    )
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = False
        with patch(
            "app.services.device_management._tcp_probe",
            side_effect=[(False, None, "refused"), (False, None, "refused")],
        ):
            with patch(
                "app.services.device_management._snmp_probe",
                return_value={"method": "snmp", "ok": True, "latency_ms": 3.5},
            ):
                result = device_management.probe_reachability(None, device)
    assert result["reachable"] is True
    assert result["method"] == "snmp"
