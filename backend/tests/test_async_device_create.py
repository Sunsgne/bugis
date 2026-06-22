"""Device create should return immediately and schedule config learn in background."""
from __future__ import annotations

import time

import pytest

from app.services import concurrent_learn


def test_create_device_schedules_background_learn(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_ids, **kwargs):
        scheduled.extend(device_ids)

    monkeypatch.setattr(concurrent_learn, "schedule_learn_devices", fake_schedule)

    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Async Create DC", "code": "ACDC", "bgp_asn": 65001},
    ).json()

    t0 = time.time()
    resp = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        params={"learn": True},
        json={
            "name": "ASYNC-CREATE-1",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "unknown",
            "mgmt_ip": "10.99.88.1",
            "site_id": site["id"],
        },
    )
    elapsed = time.time() - t0

    assert resp.status_code == 201
    body = resp.json()
    assert body["learn_scheduled"] is True
    assert scheduled == [body["id"]]
    assert elapsed < 2.0


def test_bulk_import_schedules_background_learn(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_ids, **kwargs):
        scheduled.extend(device_ids)

    monkeypatch.setattr(concurrent_learn, "schedule_learn_devices", fake_schedule)

    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Bulk Async DC", "code": "BADC", "bgp_asn": 65001},
    ).json()
    csv_body = (
        "name,vendor,model,role,overlay_tech,status,mgmt_ip,loopback_ip,bgp_asn,sr_node_sid,site_code\n"
        f"BULK-ASYNC-1,h3c,S6850,leaf,vxlan_evpn,unknown,10.99.88.2,,,,{site['code']}\n"
    )
    resp = client.post(
        "/api/v1/bulk/devices/import?learn=true",
        headers=auth_headers,
        files={"file": ("devices.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["learn"]["scheduled"] is True
    assert len(scheduled) == 1
