"""Work order audit retention + provisioning reliability fixes."""
from __future__ import annotations

import itertools

import pytest
from sqlalchemy import select

from app import worker
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import WorkOrderStatus
from app.models.workorder import WorkOrder

_seq = itertools.count(1)


def _topology(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"WR DC {n}", "code": f"WR-DC{n}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"WR Tenant {n}", "code": f"WR-TEN{n}", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"WR-H3C-{n}", "vendor": "h3c", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.31.0.{n}", "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": f"WR L2 {n}", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"],
                   "interface_name": f"GE1/0/{40 + n}"}
              ]},
    ).json()
    return circuit, dev


@pytest.fixture(autouse=True)
def _reset_provisioning_flags():
    async_flag = settings.async_provisioning
    yield
    settings.async_provisioning = async_flag


def test_work_orders_survive_circuit_delete(client, auth_headers):
    circuit, _dev = _topology(client, auth_headers)
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert wo["circuit_code"] == circuit["code"]

    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    )
    refreshed = client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).json()
    assert refreshed["status"] == "decommissioned"

    assert client.delete(
        f"/api/v1/circuits/{circuit['id']}", headers=auth_headers
    ).status_code == 204
    assert client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).status_code == 404

    listed = client.get("/api/v1/work-orders", headers=auth_headers).json()
    codes = {row["code"] for row in listed}
    assert wo["code"] in codes
    kept = next(row for row in listed if row["code"] == wo["code"])
    assert kept["circuit_code"] == circuit["code"]
    assert kept["circuit_id"] is None


def test_duplicate_provision_blocked_while_inflight(client, auth_headers):
    settings.async_provisioning = True
    circuit, _dev = _topology(client, auth_headers)

    first = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "scheduled"

    second = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert second.status_code == 409, second.text
    assert "进行中的工单" in second.json()["detail"]


def test_async_enqueue_sets_circuit_provisioning(client, auth_headers):
    settings.async_provisioning = True
    circuit, _dev = _topology(client, auth_headers)

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "scheduled"
    assert body["circuit_status"] == "provisioning"

    circ = client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).json()
    assert circ["status"] == "provisioning"


def test_recover_orphan_running_without_jobs(client, auth_headers):
    settings.async_provisioning = True
    circuit, _dev = _topology(client, auth_headers)

    r = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    wo_id = r.json()["id"]

    db = SessionLocal()
    try:
        wo = db.get(WorkOrder, wo_id)
        assert wo is not None
        wo.status = WorkOrderStatus.RUNNING
        db.commit()
    finally:
        db.close()

    requeued = worker.recover_orphaned_running()
    assert wo_id in requeued

    db = SessionLocal()
    try:
        wo = db.get(WorkOrder, wo_id)
        assert wo is not None
        assert wo.status == WorkOrderStatus.SCHEDULED
        assert any("重新加入开通队列" in e.message for e in wo.events)
    finally:
        db.close()

    worker.process_pending()
    detail = client.get(f"/api/v1/work-orders/{wo_id}", headers=auth_headers).json()
    assert detail["status"] == "completed", detail
