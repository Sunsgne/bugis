"""Tests for background circuit deletion."""
from __future__ import annotations

import itertools
import time

from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.enums import CircuitStatus, ServiceType, WorkOrderStatus, WorkOrderType
from app.models.tenant import Tenant
from app.models.workorder import WorkOrder
from app.services import circuit_delete_service
from tests.test_api import _bootstrap_topology

_seq = itertools.count(1)


def test_delete_circuit_record_removes_row():
    db = SessionLocal()
    try:
        n = next(_seq)
        tenant = Tenant(name=f"T-{n}", code=f"TEN{n}", type="enterprise")
        db.add(tenant)
        db.flush()
        circuit = Circuit(
            code=f"CIR-{n}",
            name="delete-me",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.DECOMMISSIONED,
            bandwidth_mbps=100,
        )
        db.add(circuit)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=1,
                label="A",
                interface_name="GE1/0/1",
            )
        )
        db.commit()
        circuit_id = circuit.id

        result = circuit_delete_service.delete_circuit_by_id(db, circuit_id)
        db.commit()

        assert result["circuit_id"] == circuit_id
        assert db.get(Circuit, circuit_id) is None
    finally:
        db.close()


def test_delete_circuit_retains_work_order_with_code():
    db = SessionLocal()
    try:
        n = next(_seq)
        tenant = Tenant(name=f"T-wo-{n}", code=f"TWO{n}", type="enterprise")
        db.add(tenant)
        db.flush()
        circuit = Circuit(
            code=f"CIR-WO-{n}",
            name="wo-retain",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.DECOMMISSIONED,
            bandwidth_mbps=100,
        )
        db.add(circuit)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=1,
                label="A",
                interface_name="GE1/0/1",
            )
        )
        wo = WorkOrder(
            code=f"WO-{n}",
            circuit_id=circuit.id,
            type=WorkOrderType.DECOMMISSION,
            status=WorkOrderStatus.COMPLETED,
            title="decom",
        )
        db.add(wo)
        db.commit()
        circuit_id = circuit.id
        wo_id = wo.id

        circuit_delete_service.delete_circuit_by_id(db, circuit_id)
        db.commit()

        retained = db.get(WorkOrder, wo_id)
        assert retained is not None
        assert retained.circuit_id is None
        assert retained.circuit_code == circuit.code
    finally:
        db.close()


def test_background_delete_job_status(client, auth_headers):
    _, tenant, dev_a, _ = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "bg-delete-status",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "endpoints": [
                {
                    "label": "A",
                    "device_id": dev_a["id"],
                    "interface_name": f"GE1/0/{n % 30 + 2}",
                }
            ],
        },
    ).json()
    assert "id" in circuit, circuit
    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}?wo_type=decommission",
        headers=auth_headers,
    )
    resp = client.delete(
        f"/api/v1/circuits/{circuit['id']}",
        headers=auth_headers,
        params={"background": "true"},
    )
    assert resp.status_code == 202, resp.text
    for _ in range(30):
        status = client.get(
            f"/api/v1/circuits/{circuit['id']}/delete-status",
            headers=auth_headers,
        )
        if status.status_code == 404:
            break
        assert status.status_code == 200, status.text
        body = status.json()
        if body["status"] == "failed":
            raise AssertionError(body.get("error") or "background delete failed")
        if body["status"] == "succeeded":
            break
        time.sleep(0.2)
    else:
        raise AssertionError("background delete did not complete in time")
    assert client.get(f"/api/v1/circuits/{circuit['id']}", headers=auth_headers).status_code == 404
