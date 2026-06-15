"""Device SNMP optional fields and defaults."""
from __future__ import annotations

from app.services import snmp_device


def test_snmp_defaults_endpoint(client):
    r = client.get("/api/v1/system/snmp-defaults")
    assert r.status_code == 200
    body = r.json()
    assert body["port"] == 161
    assert body["version"] == "2c"
    assert body["community"] == "bugis-ro"
    assert body["enabled"] is True


def test_create_device_with_snmp_defaults(client, auth_headers):
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "SNMP DC", "code": "SNMP-DC", "bgp_asn": 65001},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": "SNMP-LEAF-01",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": "10.9.0.11",
            "site_id": site["id"],
            "snmp_enabled": True,
            "snmp_port": 161,
            "snmp_version": "2c",
        },
    ).json()
    assert dev["snmp_enabled"] is True
    assert dev["snmp_port"] == 161
    assert dev["snmp_community_set"] is False

    from app.core.database import SessionLocal
    from app.models.device import Device

    db = SessionLocal()
    try:
        device = db.get(Device, dev["id"])
        eff = snmp_device.effective_snmp(device)
        assert eff["community"] == "bugis-ro"
    finally:
        db.close()


def test_create_device_snmp_disabled(client, auth_headers):
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": "NO-SNMP-01",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": "10.9.0.12",
            "snmp_enabled": False,
        },
    ).json()
    assert dev["snmp_enabled"] is False
