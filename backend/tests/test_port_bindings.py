"""Tests for device port binding listing."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device
from app.services import port_inventory

_seq = itertools.count(1)


def _site(client, auth_headers):
    n = next(_seq)
    return client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Bind DC {n}", "code": f"B-DC{n}", "bgp_asn": 65001},
    ).json()


def test_device_port_bindings_api(client, auth_headers):
    site = _site(client, auth_headers)
    n = next(_seq)
    device = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"BIND-LEAF-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": f"10.9.{n}.11",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Bind Tenant {n}", "code": f"BT{n}"},
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": f"Bind Circuit {n}",
            "code": f"BC{n:04d}",
            "tenant_id": tenant["id"],
            "bandwidth_mbps": 100,
            "endpoints": [
                {
                    "device_id": device["id"],
                    "label": "A",
                    "interface_name": "GE1/0/5",
                    "access_mode": "dot1q",
                    "vlan_id": 120,
                }
            ],
        },
    ).json()

    resp = client.get(
        f"/api/v1/devices/{device['id']}/port-bindings",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["platform_bindings"] == 1
    assert body["items"][0]["tenant_code"] == tenant["code"]
    assert body["items"][0]["circuit_code"] == circuit["code"]
    assert body["items"][0]["interface_name"] == "GE1/0/5"
    assert body["items"][0]["s_vid"] == 120


def test_list_port_bindings_merges_device_usage():
    from app.models.circuit import Circuit, CircuitEndpoint
    from app.models.device import DeviceInterface
    from app.models.enums import AccessMode, CircuitStatus, ServiceType, Vendor
    from app.models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = Tenant(name="T1", code="T1")
        device = Device(
            name="DEV1",
            vendor=Vendor.H3C,
            mgmt_ip="10.0.0.1",
        )
        db.add_all([tenant, device])
        db.flush()
        circuit = Circuit(
            name="C1",
            code="C0001",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.ACTIVE,
            bandwidth_mbps=100,
        )
        db.add(circuit)
        db.flush()
        db.add(
            CircuitEndpoint(
                circuit_id=circuit.id,
                device_id=device.id,
                label="A",
                interface_name="GE1/0/1",
                access_mode=AccessMode.DOT1Q,
                vlan_id=100,
            )
        )
        db.add(
            DeviceInterface(
                device_id=device.id,
                name="GE1/0/2",
                used_s_vids=[
                    {
                        "s_vid": 200,
                        "c_vid": None,
                        "access_mode": "dot1q",
                        "source": "device",
                    }
                ],
                allocated=True,
            )
        )
        db.commit()

        result = port_inventory.list_port_bindings(db, device)
        assert result["platform_bindings"] == 1
        assert result["device_only_bindings"] == 1
        assert len(result["items"]) == 2
    finally:
        db.close()
