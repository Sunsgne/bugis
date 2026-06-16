"""Tests for per-endpoint interface description."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import AccessMode, CircuitStatus, ServiceType, Vendor
from app.models.tenant import Tenant
from app.services import port_inventory

_seq = itertools.count(1)


def test_circuit_create_persists_interface_description(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Desc DC {n}", "code": f"D-DC{n}", "bgp_asn": 65001},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Desc Tenant {n}", "code": f"DT{n}"},
    ).json()
    device = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"DESC-LEAF-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": f"10.8.{n}.11",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": f"Desc Circuit {n}",
            "tenant_id": tenant["id"],
            "bandwidth_mbps": 100,
            "endpoints": [
                {
                    "device_id": device["id"],
                    "label": "A",
                    "interface_name": "GE1/0/10",
                    "access_mode": "dot1q",
                    "vlan_id": 4008,
                    "interface_description": "ruiyou-sha-tyo-4008",
                }
            ],
        },
    ).json()
    assert circuit["endpoints"][0]["interface_description"] == "ruiyou-sha-tyo-4008"


def test_h3c_rendered_config_uses_endpoint_interface_description(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Desc DC2 {n}", "code": f"D2-DC{n}", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Desc Tenant2 {n}", "code": f"DT2{n}", "type": "enterprise"},
    ).json()
    dev_h3c = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"T-H3C-DESC-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.10.{n}.1",
            "bgp_asn": 65010,
            "site_id": site["id"],
        },
    ).json()
    huawei = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"HW-DESC-{next(_seq)}",
            "vendor": "huawei",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": "10.99.1.1",
            "bgp_asn": 65010,
            "site_id": site["id"],
        },
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Iface Desc Circuit",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 200,
            "endpoints": [
                {
                    "label": "A",
                    "device_id": dev_h3c["id"],
                    "interface_name": "GE1/0/5",
                    "vlan_id": 4008,
                    "interface_description": "ruiyou-sha-tyo-4008",
                },
                {
                    "label": "Z",
                    "device_id": huawei["id"],
                    "interface_name": "10GE1/0/5",
                    "vlan_id": 4008,
                    "interface_description": "ruiyou-sha-tyo-4008",
                },
            ],
        },
    ).json()
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    cfgs = {j["device_id"]: j["rendered_config"] for j in wo["config_jobs"]}
    h3c = cfgs[dev_h3c["id"]]
    hw = cfgs[huawei["id"]]
    assert "description ruiyou-sha-tyo-4008" in h3c
    si = h3c.index("service-instance")
    desc = h3c.index("description ruiyou-sha-tyo-4008")
    enc = h3c.index("encapsulation s-vid")
    assert si < desc < enc
    assert "description ruiyou-sha-tyo-4008" in hw
    assert hw.index("interface 10GE1/0/5.4008") < hw.index(
        "description ruiyou-sha-tyo-4008"
    )


def test_vsi_description_uses_tenant_code_and_rd_matches_vni(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"VSI DC {n}", "code": f"V-DC{n}", "bgp_asn": 65001},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": "天网恢恢", "code": f"TIANWANG{n}", "type": "enterprise"},
    ).json()
    dev_h3c = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"VSI-H3C-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.12.{n}.1",
            "bgp_asn": 65001,
            "site_id": site["id"],
        },
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "test",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 100,
            "endpoints": [
                {
                    "label": "A",
                    "device_id": dev_h3c["id"],
                    "interface_name": "GE1/0/30",
                    "vlan_id": 1234,
                }
            ],
        },
    )
    assert circuit.status_code == 201, circuit.text
    circuit = circuit.json()
    vni = circuit["vni"]
    rd = circuit["route_distinguisher"]
    assert rd == f"65001:{vni}"
    wo = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    h3c = next(j["rendered_config"] for j in wo["config_jobs"] if j["device_id"] == dev_h3c["id"])
    assert f"description {tenant['code']} · test [{circuit['code']}]" in h3c
    assert "tenant=" not in h3c
    assert f"route-distinguisher {rd}" in h3c
    assert f"vpn-target {circuit['route_target']} import-extcommunity" in h3c
    assert f"vpn-target {circuit['route_target']} export-extcommunity" in h3c


def test_platform_port_bindings_use_endpoint_interface_description():
    db = SessionLocal()
    try:
        tenant = Tenant(name="T1", code="T1")
        device = Device(name="DEV1", vendor=Vendor.H3C, mgmt_ip="10.0.0.1")
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
                interface_description="customer-ac-100",
            )
        )
        db.commit()

        result = port_inventory.list_port_bindings(db, device)
        assert result["items"][0]["description"] == "customer-ac-100"
    finally:
        db.close()
