"""Reachability probe tries SSH, NETCONF, then SNMP."""
from __future__ import annotations

from unittest.mock import patch

from app.models.device import Device
from app.models.enums import Vendor
from app.services import device_management


def test_probe_reachability_dry_run_simulated_when_all_fail():
    """When every real probe fails in dry-run, fall back to simulated primary reachability."""
    device = Device(
        name="t",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        mgmt_ip_backup="203.0.113.10",
    )
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = True
        with patch(
            "app.services.device_management._tcp_probe",
            return_value=(False, None, "timeout"),
        ):
            with patch(
                "app.services.device_management._snmp_probe",
                return_value={"method": "snmp", "ok": False, "skipped": True},
            ):
                result = device_management.probe_reachability(None, device)
    assert result["reachable"] is True
    assert result["method"] == "dry_run"
    assert result["mgmt_ip_active"] == "10.0.0.1"


def test_probe_reachability_dry_run_still_tcp():
    """Dry-run attempts real TCP/SNMP before simulated fallback."""
    device = Device(name="t", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = True
        with patch(
            "app.services.device_management._tcp_probe",
            side_effect=[(True, 2.5, None)],
        ):
            result = device_management.probe_reachability(None, device)
    assert result["reachable"] is True
    assert result["method"] == "tcp_ssh"
    assert result["dry_run"] is True


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
