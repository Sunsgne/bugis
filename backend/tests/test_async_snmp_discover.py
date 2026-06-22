"""Tests for background parallel SNMP interface discovery."""
from __future__ import annotations

import itertools

from app.services import concurrent_snmp_discover

_seq = itertools.count(1)


def test_discover_interfaces_background_returns_immediately(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_id: int) -> None:
        scheduled.append(device_id)

    monkeypatch.setattr(concurrent_snmp_discover, "schedule_snmp_discover", fake_schedule)

    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"DC {n}", "code": f"DC{n}", "bgp_asn": 65010},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"SW-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "mgmt_ip": f"10.40.{n}.1",
            "site_id": site["id"],
            "snmp_enabled": True,
        },
        params={"learn": "false"},
    ).json()

    resp = client.post(
        f"/api/v1/devices/{dev['id']}/discover-interfaces",
        headers=auth_headers,
        params={"background": "true"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scheduled"] is True
    assert body["device_id"] == dev["id"]
    assert scheduled == [dev["id"]]


def test_discover_interfaces_batch(client, auth_headers, monkeypatch):
    scheduled: list[int] = []

    def fake_schedule(device_ids, *, max_workers=None):
        scheduled.extend(device_ids)

    monkeypatch.setattr(concurrent_snmp_discover, "schedule_snmp_discovers", fake_schedule)

    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"DC2 {n}", "code": f"DC2{n}", "bgp_asn": 65010},
    ).json()
    ids = []
    for i in range(2):
        dev = client.post(
            "/api/v1/devices",
            headers=auth_headers,
            json={
                "name": f"SW2-{n}-{i}",
                "vendor": "h3c",
                "role": "leaf",
                "mgmt_ip": f"10.41.{n}.{i}",
                "site_id": site["id"],
                "snmp_enabled": True,
            },
            params={"learn": "false"},
        ).json()
        ids.append(dev["id"])

    resp = client.post(
        "/api/v1/devices/discover-interfaces-batch",
        headers=auth_headers,
        json={"device_ids": ids},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scheduled"] == 2
    assert set(scheduled) == set(ids)


def test_discover_interfaces_sync_still_works(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"DC3 {n}", "code": f"DC3{n}", "bgp_asn": 65010},
    ).json()
    dev = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"SW3-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "mgmt_ip": f"10.42.{n}.1",
            "site_id": site["id"],
            "snmp_enabled": True,
        },
        params={"learn": "false"},
    ).json()

    resp = client.post(
        f"/api/v1/devices/{dev['id']}/discover-interfaces",
        headers=auth_headers,
        params={"background": "false"},
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
