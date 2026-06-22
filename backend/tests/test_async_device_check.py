"""Background device reachability + S-VID check."""
from __future__ import annotations

import time

from app.services import concurrent_device_check


def test_check_device_schedules_background(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_ids, **kwargs):
        scheduled.extend(device_ids)

    monkeypatch.setattr(concurrent_device_check, "schedule_device_checks", fake_schedule)

    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Check Async DC", "code": "CADC", "bgp_asn": 65001},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        params={"learn": False},
        json={
            "name": "CHECK-ASYNC-1",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "unknown",
            "mgmt_ip": "10.99.77.1",
            "site_id": site["id"],
        },
    ).json()

    t0 = time.time()
    r = client.post(
        f"/api/v1/devices/{dev['id']}/check",
        headers=auth_headers,
        params={"background": True},
    )
    elapsed = time.time() - t0

    assert r.status_code == 200
    body = r.json()
    assert body["scheduled"] is True
    assert body["device_id"] == dev["id"]
    assert scheduled == [dev["id"]]
    assert elapsed < 2.0


def test_check_batch_api(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_ids, **kwargs):
        scheduled.extend(device_ids)

    monkeypatch.setattr(concurrent_device_check, "schedule_device_checks", fake_schedule)

    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Check Batch DC", "code": "CBDC", "bgp_asn": 65001},
    ).json()
    ids = []
    for i in range(2):
        dev = client.post(
            "/api/v1/devices",
            headers=auth_headers,
            params={"learn": False},
            json={
                "name": f"CHECK-BATCH-{i}",
                "vendor": "h3c",
                "role": "leaf",
                "overlay_tech": "vxlan_evpn",
                "status": "unknown",
                "mgmt_ip": f"10.99.76.{i + 1}",
                "site_id": site["id"],
            },
        ).json()
        ids.append(dev["id"])

    r = client.post(
        "/api/v1/devices/check-batch",
        headers=auth_headers,
        json={"device_ids": ids},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scheduled"] == 2
    assert set(scheduled) == set(ids)
