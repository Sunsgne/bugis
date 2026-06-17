"""Demo control-plane sync for active circuits."""
from __future__ import annotations

from app.core.database import SessionLocal
from app.models.controlplane import EvpnRoute
from scripts.demo_data import sync_active_circuit_controlplane
from tests.test_api import _bootstrap_topology


def test_sync_active_circuit_controlplane_installs_routes(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)

    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "ctrl sync",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 1000,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/3"},
                {"label": "Z", "device_id": dev_z["id"], "interface_name": "GE1/0/3"},
            ],
        },
    ).json()
    # Activate via the work-order provision flow (status is not directly
    # editable through PATCH — lifecycle transitions go through orchestration).
    provisioned = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert provisioned["circuit_status"] == "active"

    db = SessionLocal()
    try:
        assert (
            db.query(EvpnRoute)
            .filter(EvpnRoute.circuit_id == circuit["id"])
            .count()
            == 0
        )
        synced = sync_active_circuit_controlplane(db)
        assert synced >= 1
        assert (
            db.query(EvpnRoute)
            .filter(EvpnRoute.circuit_id == circuit["id"])
            .count()
            > 0
        )
    finally:
        db.close()

    status = client.get("/api/v1/controller/status", headers=auth_headers).json()
    assert status["route_count"] > 0
    assert status["vtep_count"] > 0
    assert status["vni_count"] > 0
