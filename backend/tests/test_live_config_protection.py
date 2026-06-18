"""Live-config overwrite protection: settings, pre-push refresh & baseline guard."""
from __future__ import annotations

from sqlalchemy import delete, select

from app.models.circuit import Circuit
from app.models.config_snapshot import DeviceConfigSnapshot
from app.services import orchestrator


def _bootstrap(client, auth_headers, tag: str):
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"Guard DC {tag}", "code": f"GD{tag}", "city": "SH"},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"Guard Tenant {tag}", "code": f"GT{tag}", "tenant_type": "enterprise"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={
            "name": f"guard-leaf-{tag}", "vendor": "h3c", "role": "leaf",
            "overlay_tech": "vxlan_evpn", "mgmt_ip": f"10.90.0.{tag}",
            "site_id": site["id"],
        },
    ).json()
    return tenant, dev


def test_protect_live_config_setting_default_and_update(client, auth_headers):
    cur = client.get("/api/v1/system/settings", headers=auth_headers).json()
    assert cur["platform"]["protect_live_config"] is True

    off = client.patch(
        "/api/v1/system/settings/platform",
        headers=auth_headers,
        json={"protect_live_config": False},
    )
    assert off.status_code == 200
    assert off.json()["protect_live_config"] is False

    # restore
    client.patch(
        "/api/v1/system/settings/platform",
        headers=auth_headers,
        json={"protect_live_config": True},
    )


def test_devices_without_baseline_helper(client, auth_headers):
    from app.core.database import SessionLocal
    from app.services import config_mgmt

    tenant, dev = _bootstrap(client, auth_headers, "31")
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "Guard L2", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "endpoints": [
                {"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/21"},
            ],
        },
    ).json()

    db = SessionLocal()
    try:
        # Remove any learned baseline that auto-learn-on-import created.
        db.execute(
            delete(DeviceConfigSnapshot).where(
                DeviceConfigSnapshot.device_id == dev["id"],
                DeviceConfigSnapshot.source == "learn",
            )
        )
        db.commit()
        c = db.execute(
            select(Circuit).where(Circuit.id == circuit["id"])
        ).scalar_one()
        missing = orchestrator._devices_without_baseline(db, c)
        assert dev["name"] in missing

        # After a learn snapshot exists, the device is no longer flagged.
        device = c.endpoints[0].device
        config_mgmt.add_snapshot(db, device, "interface GE1/0/21\n", source="learn")
        db.commit()
        assert orchestrator._devices_without_baseline(db, c) == []
    finally:
        db.close()


def test_refresh_live_inventory_does_no_device_io(client, auth_headers, monkeypatch):
    """The pre-push refresh must rely on cached config only (no switch load)."""
    from app.core.database import SessionLocal

    tenant, dev = _bootstrap(client, auth_headers, "32")
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "Guard L2b", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "endpoints": [
                {"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/22"},
            ],
        },
    ).json()

    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("refresh must not fetch live config from device")

    monkeypatch.setattr("app.services.config_fetch.fetch_running_config", _boom)

    db = SessionLocal()
    try:
        c = db.execute(select(Circuit).where(Circuit.id == circuit["id"])).scalar_one()
        # Should complete without touching the device.
        orchestrator._refresh_live_inventory(db, c)
    finally:
        db.close()


def test_provision_logs_live_config_protection_warning(client, auth_headers):
    from app.core.database import SessionLocal

    tenant, dev = _bootstrap(client, auth_headers, "33")
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={
            "name": "Guard L2c", "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
            "endpoints": [
                {"label": "A", "device_id": dev["id"], "interface_name": "GE1/0/23"},
            ],
        },
    ).json()

    db = SessionLocal()
    try:
        db.execute(
            delete(DeviceConfigSnapshot).where(
                DeviceConfigSnapshot.device_id == dev["id"],
                DeviceConfigSnapshot.source == "learn",
            )
        )
        db.commit()
    finally:
        db.close()

    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["status"] == "completed"
    messages = "\n".join(e["message"] for e in wo.get("events", []))
    assert "现网配置保护" in messages
