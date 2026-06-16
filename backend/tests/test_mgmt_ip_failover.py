"""Dual management IP failover tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.device import Device
from app.models.enums import Vendor
from app.services import device_management, snmp


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


def test_ensure_snmp_mgmt_ip_failover_huawei():
    device = Device(
        name="hw-pe",
        vendor=Vendor.HUAWEI,
        mgmt_ip="10.1.1.1",
        mgmt_ip_backup="203.0.113.20",
        mgmt_ip_primary_label="管理网",
        mgmt_ip_backup_label="公网",
        snmp_enabled=True,
    )
    mock_cfg = type("Cfg", (), {"enabled": True, "port": 161})()

    def fake_snmp(db, dev, host, *, port=None):
        if host == "10.1.1.1":
            return {"method": "snmp", "ok": False, "error": "timeout", "host": host}
        if host == "203.0.113.20":
            return {"method": "snmp", "ok": True, "latency_ms": 4.2, "host": host}
        return {"method": "snmp", "ok": False, "host": host}

    with patch("app.services.snmp_settings.get_or_create", return_value=mock_cfg):
        with patch("app.services.snmp_device.effective_snmp", return_value={"enabled": True, "port": 161}):
            with patch("app.services.device_management._snmp_probe", side_effect=fake_snmp):
                host = device_management.ensure_snmp_mgmt_ip(object(), device, persist=True)

    assert host == "203.0.113.20"
    assert device.mgmt_ip_active == "203.0.113.20"
    assert device.mgmt_ip_active_role == "backup"


def test_ensure_reachable_raises_with_candidate_ips():
    device = Device(
        name="edge",
        vendor=Vendor.HUAWEI,
        mgmt_ip="10.0.0.1",
        mgmt_ip_backup="203.0.113.10",
        mgmt_ip_primary_label="管理网",
        mgmt_ip_backup_label="公网",
    )
    with patch("app.services.device_management.settings") as mock_settings:
        mock_settings.dry_run = False
        with patch(
            "app.services.device_management._tcp_probe",
            return_value=(False, None, "timeout"),
        ):
            with patch(
                "app.services.device_management._snmp_probe",
                return_value={"method": "snmp", "ok": False, "skipped": True},
            ):
                with pytest.raises(device_management.MgmtUnreachableError) as exc:
                    device_management.ensure_reachable_mgmt_ip(None, device, persist=False)

    assert "10.0.0.1" in str(exc.value)
    assert "203.0.113.10" in str(exc.value)


def test_walk_with_mgmt_failover_uses_backup():
    device = Device(
        name="hw-sw",
        vendor=Vendor.HUAWEI,
        mgmt_ip="10.0.0.1",
        mgmt_ip_backup="203.0.113.55",
        snmp_enabled=True,
    )
    walk_calls: list[str | None] = []

    def fake_walk_real(dev, cfg, community, *, port=None, host=None):
        walk_calls.append(host)
        return [{
            "name": "10GE1/0/1",
            "description": None,
            "speed_mbps": 10000,
            "oper_status": "up",
            "ifindex": 1,
            "discovered_via": "snmp",
        }]

    mock_cfg = type("Cfg", (), {"port": 161})()

    with patch(
        "app.services.device_management.resolve_snmp_endpoint",
        return_value=("203.0.113.55", 161, {"ip": "203.0.113.55", "role": "backup", "label": "公网"}),
    ):
        with patch("app.services.snmp._walk_real", side_effect=fake_walk_real):
            results, used = snmp._walk_with_mgmt_failover(object(), device, mock_cfg, "public")

    assert used is not None
    assert used["ip"] == "203.0.113.55"
    assert results[0]["name"] == "10GE1/0/1"
    assert device.mgmt_ip_active == "203.0.113.55"
    assert walk_calls == ["203.0.113.55"]


def test_discover_interfaces_api_failover(client: TestClient, auth_headers: dict):
    payload = {
        "name": "cs-1-test",
        "vendor": "huawei",
        "mgmt_ip": "10.0.0.1",
        "mgmt_ip_backup": "203.0.113.99",
        "mgmt_ip_primary_label": "管理网",
        "mgmt_ip_backup_label": "公网",
        "username": "admin",
        "password": "admin",
        "snmp_enabled": True,
    }
    r = client.post("/api/v1/devices", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    dev_id = r.json()["id"]

    def fake_walk_real(dev, cfg, community, *, port=None, host=None):
        if host == "10.0.0.1":
            raise RuntimeError("primary SNMP failed")
        return [{
            "name": "GE1/0/2",
            "description": "uplink",
            "speed_mbps": 10000,
            "oper_status": "up",
            "ifindex": 2,
            "discovered_via": "snmp",
        }]

    def fake_snmp(db, dev, host, *, port=None):
        if host == "10.0.0.1":
            return {"method": "snmp", "ok": False, "error": "timeout"}
        return {"method": "snmp", "ok": True}

    with patch("app.services.device_management._snmp_probe", side_effect=fake_snmp):
        with patch("app.services.snmp._walk_real", side_effect=fake_walk_real):
            r = client.post(
                f"/api/v1/devices/{dev_id}/discover-interfaces",
                headers=auth_headers,
            )

    assert r.status_code == 200, r.text
    data = r.json()
    assert any(i["name"] == "GE1/0/2" for i in data)

    dev = client.get(f"/api/v1/devices/{dev_id}", headers=auth_headers).json()
    assert dev["mgmt_ip_active"] == "203.0.113.99"
    assert dev["mgmt_ip_active_role"] == "backup"


def test_probe_host_huawei_snmp_tries_16161():
    device = Device(
        name="hw",
        vendor=Vendor.HUAWEI,
        mgmt_ip="10.88.91.1",
        snmp_enabled=True,
    )
    attempts: list[int | None] = []

    def fake_snmp(db, dev, host, *, port=None):
        attempts.append(port)
        if port == 16161:
            return {"method": "snmp", "ok": True, "latency_ms": 2.0, "host": host, "port": port}
        return {"method": "snmp", "ok": False, "error": "timeout", "host": host, "port": port}

    mock_cfg = type("Cfg", (), {"enabled": True, "port": 161})()

    with patch(
        "app.services.device_management._tcp_probe",
        return_value=(False, None, "timeout"),
    ):
        with patch("app.services.snmp_settings.get_or_create", return_value=mock_cfg):
            with patch(
                "app.services.snmp_device.effective_snmp",
                return_value={"enabled": True, "port": 161},
            ):
                with patch("app.services.device_management._snmp_probe", side_effect=fake_snmp):
                    result = device_management._probe_host(object(), device, "10.88.91.1", "primary", "管理网")

    assert result is not None
    assert result["reachable"] is True
    assert result["method"] == "snmp"
    assert 16161 in attempts


def test_fetch_running_config_failover_to_backup():
    from app.services import config_fetch

    device = Device(
        name="edge",
        vendor=Vendor.H3C,
        mgmt_ip="10.0.0.1",
        mgmt_ip_backup="203.0.113.10",
        mgmt_ip_active="10.0.0.1",
        mgmt_ip_active_role="primary",
    )
    fetch_hosts: list[str] = []

    def fake_fetch(dev, dry_run=False, transport=None, allow_transport_fallback=False):
        from app.drivers.base import DriverResult

        host = dev.active_mgmt_ip
        fetch_hosts.append(host)
        if host == "10.0.0.1":
            return DriverResult(success=False, output="primary fetch failed", dry_run=dry_run)
        return DriverResult(
            success=True,
            config=(
                "sysname BACKUP\n"
                "interface GE1/0/1\n"
                " description backup-fetch\n"
                " port link-mode route\n"
                " ip address 10.0.0.1 255.255.255.0\n"
                "bgp 65001\n"
                " router-id 10.0.0.1\n"
                "return\n"
            ),
            dry_run=dry_run,
        )

    with patch.object(config_fetch.settings, "dry_run", False):
        with patch(
            "app.services.device_management.probe_reachability",
            return_value={"reachable": True, "mgmt_ip_active": "10.0.0.1"},
        ):
            with patch("app.services.config_fetch.get_driver") as mock_driver:
                mock_driver.return_value.fetch_config.side_effect = fake_fetch
                ok, content, err = config_fetch.fetch_running_config(device, db=object())

    assert ok is True, err
    assert "backup-fetch" in content
    assert fetch_hosts[0] == "10.0.0.1"
    assert "203.0.113.10" in fetch_hosts
    assert device.mgmt_ip_active == "203.0.113.10"
    assert device.mgmt_ip_active_role == "backup"


def test_resolve_snmp_huawei_tries_port_16161():
    device = Device(
        name="hw-ce",
        vendor=Vendor.HUAWEI,
        mgmt_ip="10.88.91.1",
        snmp_enabled=True,
        snmp_port=161,
    )
    mock_cfg = type("Cfg", (), {"enabled": True, "port": 161})()
    attempts: list[int] = []

    def fake_snmp(db, dev, host, *, port=None):
        attempts.append(port or 161)
        if port == 16161:
            return {"method": "snmp", "ok": True, "latency_ms": 3.0, "host": host, "port": port}
        return {"method": "snmp", "ok": False, "error": "timeout", "host": host, "port": port}

    with patch("app.services.snmp_settings.get_or_create", return_value=mock_cfg):
        with patch("app.services.snmp_device.effective_snmp", return_value={"enabled": True, "port": 161}):
            with patch("app.services.device_management._snmp_probe", side_effect=fake_snmp):
                host, port, _cand = device_management.resolve_snmp_endpoint(object(), device)

    assert host == "10.88.91.1"
    assert port == 16161
    assert 16161 in attempts
