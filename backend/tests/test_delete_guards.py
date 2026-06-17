"""Reference-integrity guards for destructive deletes and PATCH status lock."""
from __future__ import annotations

from tests.test_api import _bootstrap_topology


def _circuit(client, auth_headers, tenant, dev_a, dev_z):
    return client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "guard circuit",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 1000,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/3"},
                {"label": "Z", "device_id": dev_z["id"], "interface_name": "GE1/0/3"},
            ],
        },
    ).json()


def test_delete_site_blocked_when_devices_exist(client, auth_headers):
    site, _tenant, _a, _z = _bootstrap_topology(client, auth_headers)
    r = client.delete(f"/api/v1/sites/{site['id']}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_site_ok_when_empty(client, auth_headers):
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Empty DC", "code": "EMPTY-DC", "bgp_asn": 65055},
    ).json()
    r = client.delete(f"/api/v1/sites/{site['id']}", headers=auth_headers)
    assert r.status_code == 204


def test_delete_device_blocked_by_active_circuit(client, auth_headers):
    _site, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    _circuit(client, auth_headers, tenant, dev_a, dev_z)
    r = client.delete(f"/api/v1/devices/{dev_a['id']}", headers=auth_headers)
    assert r.status_code == 409


def test_delete_tenant_blocked_by_active_circuit(client, auth_headers):
    _site, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    _circuit(client, auth_headers, tenant, dev_a, dev_z)
    r = client.delete(f"/api/v1/tenants/{tenant['id']}", headers=auth_headers)
    assert r.status_code == 409


def test_patch_circuit_cannot_change_status(client, auth_headers):
    _site, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    circuit = _circuit(client, auth_headers, tenant, dev_a, dev_z)
    assert circuit["status"] == "draft"
    # status is dropped from the update schema (extra="ignore"), so PATCH must
    # leave the circuit in draft — it cannot jump straight to active.
    r = client.patch(
        f"/api/v1/circuits/{circuit['id']}",
        headers=auth_headers,
        json={"status": "active", "bandwidth_mbps": 2000},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "draft"
    assert body["bandwidth_mbps"] == 2000


def test_patch_circuit_response_includes_path_fields(client, auth_headers):
    _site, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    circuit = _circuit(client, auth_headers, tenant, dev_a, dev_z)
    r = client.patch(
        f"/api/v1/circuits/{circuit['id']}",
        headers=auth_headers,
        json={"bandwidth_mbps": 1500},
    )
    assert r.status_code == 200
    body = r.json()
    # _to_circuit_out always populates these (consistent with GET/POST).
    assert "segment_list" in body
    assert "path_hops" in body
