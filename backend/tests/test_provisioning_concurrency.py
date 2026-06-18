"""Tests for async provisioning worker + pre-change config snapshots."""
from __future__ import annotations

import itertools

import pytest

from app import worker
from app.core.config import settings

_seq = itertools.count(1)


def _topology(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"PC DC {n}", "code": f"PC-DC{n}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"PC Tenant {n}", "code": f"PC-TEN{n}", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"PC-H3C-{n}", "vendor": "h3c", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.30.0.{n}", "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": f"PC L2 {n}", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"],
                   "interface_name": f"GE1/0/{30 + n}"}
              ]},
    ).json()
    return circuit, dev


@pytest.fixture(autouse=True)
def _reset_provisioning_flags():
    snap = settings.snapshot_before_change
    async_flag = settings.async_provisioning
    yield
    settings.snapshot_before_change = snap
    settings.async_provisioning = async_flag


def test_pre_change_snapshot_captured(client, auth_headers):
    settings.snapshot_before_change = True
    settings.async_provisioning = False
    circuit, dev = _topology(client, auth_headers)

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["circuit_status"] == "active"

    snaps = client.get(
        f"/api/v1/config/devices/{dev['id']}/snapshots", headers=auth_headers
    ).json()
    sources = [s["source"] for s in snaps]
    assert "pre_change" in sources, sources
    # The work order timeline records the pre-change snapshot.
    wo = r.json()
    assert any("变更前现网配置快照" in e["message"] for e in wo["events"]), wo["events"]


def test_pre_change_snapshot_can_be_disabled(client, auth_headers):
    settings.snapshot_before_change = False
    settings.async_provisioning = False
    circuit, dev = _topology(client, auth_headers)

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    snaps = client.get(
        f"/api/v1/config/devices/{dev['id']}/snapshots", headers=auth_headers
    ).json()
    assert "pre_change" not in [s["source"] for s in snaps]


def test_async_provision_enqueues_then_worker_completes(client, auth_headers):
    settings.async_provisioning = True
    circuit, _dev = _topology(client, auth_headers)

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # The request returns immediately with a queued work order (not executed
    # inline), so the request thread is never held by the device push.
    assert body["status"] == "scheduled", body
    assert body["circuit_status"] != "active"

    wo_id = body["id"]
    # Drain the queue the way the background worker would.
    processed = worker.process_pending()
    assert processed >= 1

    detail = client.get(f"/api/v1/work-orders/{wo_id}", headers=auth_headers).json()
    assert detail["status"] == "completed", detail
    circ = client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).json()
    assert circ["status"] == "active"


def test_async_decommission_enqueues(client, auth_headers):
    settings.async_provisioning = True
    circuit, _dev = _topology(client, auth_headers)
    # Provision first (async), drain.
    client.post(f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers)
    worker.process_pending()

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "scheduled"
    worker.process_pending()
    circ = client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).json()
    assert circ["status"] == "decommissioned"


def test_sync_provision_still_default(client, auth_headers):
    """With async disabled (default) provisioning stays synchronous/one-shot."""
    settings.async_provisioning = False
    circuit, _dev = _topology(client, auth_headers)
    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "completed"


def test_worker_status_endpoint(client, auth_headers):
    r = client.get("/api/v1/system/worker", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "enabled" in data and "max_concurrency" in data and "pending" in data
