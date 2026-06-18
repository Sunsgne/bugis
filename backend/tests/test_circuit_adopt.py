"""Tests for adopting on-box S-VID bindings without config push."""
from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

_seq = itertools.count(1)


def _bootstrap(client: TestClient, headers: dict):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=headers,
        json={"name": f"DC {n}", "code": f"DC{n}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={"name": f"T {n}", "code": f"TEN{n}", "type": "enterprise"},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "name": f"H3C-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.20.{n}.1",
            "bgp_asn": 65010,
            "site_id": site["id"],
        },
        params={"learn": "true"},
    ).json()
    return tenant, dev


def test_adopt_existing_svid_without_push(client, auth_headers):
    tenant, dev = _bootstrap(client, auth_headers)
    bindings = client.get(
        f"/api/v1/devices/{dev['id']}/port-bindings",
        headers=auth_headers,
        params={"scan": "true"},
    ).json()
    device_rows = [
        row for row in bindings["items"]
        if row.get("binding_type") == "device" and not row.get("circuit_id")
    ]
    assert device_rows, "expected learned on-box S-VID from dry-run fallback config"
    row = device_rows[0]

    adopted = client.post(
        "/api/v1/circuits/adopt-from-inventory",
        headers=auth_headers,
        json={
            "name": "Imported legacy service",
            "tenant_id": tenant["id"],
            "bindings": [
                {
                    "device_id": dev["id"],
                    "label": "A",
                    "interface_name": row["interface_name"],
                    "access_mode": row.get("access_mode") or "dot1q",
                    "vlan_id": row.get("s_vid"),
                    "inner_vlan_id": row.get("c_vid"),
                }
            ],
        },
    )
    assert adopted.status_code == 201, adopted.text
    body = adopted.json()
    assert body["adopted"] is True
    assert body["status"] == "active"

    wo = client.post(
        f"/api/v1/work-orders/provision/{body['id']}",
        headers=auth_headers,
    ).json()
    assert wo["status"] == "completed"
    assert wo.get("circuit_status") == "active"
    assert not wo.get("config_jobs")

    # Extend adopted circuit with a Z endpoint — platform only, no config push.
    from app.core.database import SessionLocal
    from app.models.device import DeviceInterface

    n = next(_seq)
    dev2 = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"H3C-Z-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.21.{n}.2",
            "bgp_asn": 65010,
            "site_id": dev["site_id"],
        },
        params={"learn": "false"},
    ).json()
    z_iface = "GE1/0/20"
    z_svid = row.get("s_vid") or 100
    db = SessionLocal()
    try:
        db.add(
            DeviceInterface(
                device_id=dev2["id"],
                name=z_iface,
                used_s_vids=[
                    {
                        "s_vid": z_svid,
                        "access_mode": row.get("access_mode") or "dot1q",
                        "source": "device",
                        "vni": body.get("vni"),
                        "vsi_name": body.get("vsi_name"),
                    }
                ],
                allocated=True,
            )
        )
        db.commit()
    finally:
        db.close()

    a_ep = body["endpoints"][0]
    updated = client.put(
        f"/api/v1/circuits/{body['id']}/endpoints",
        headers=auth_headers,
        json={
            "endpoints": [
                {
                    "label": a_ep["label"],
                    "device_id": a_ep["device_id"],
                    "interface_name": a_ep["interface_name"],
                    "access_mode": a_ep.get("access_mode") or "dot1q",
                    "vlan_id": a_ep.get("vlan_id"),
                    "inner_vlan_id": a_ep.get("inner_vlan_id"),
                },
                {
                    "label": "Z",
                    "device_id": dev2["id"],
                    "interface_name": z_iface,
                    "access_mode": row.get("access_mode") or "dot1q",
                    "vlan_id": z_svid,
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert len(updated.json()["endpoints"]) == 2

    wo2 = client.post(
        f"/api/v1/work-orders/provision/{body['id']}?wo_type=modify",
        headers=auth_headers,
    ).json()
    assert wo2["status"] == "completed"
    assert not wo2.get("config_jobs")


def test_scheduled_learn_endpoint(client, auth_headers):
    from app import scheduler

    before = scheduler.status().get("ticks", 0)
    client.post("/api/v1/system/scheduler/tick", headers=auth_headers)
    after = scheduler.status()
    assert after.get("ticks", 0) >= before
