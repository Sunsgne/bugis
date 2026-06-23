"""Tests for three-layer forwarding path API."""
from __future__ import annotations

import itertools

_seq = itertools.count(1)


def _bootstrap_path_topology(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"FP DC {n}", "code": f"FP{n}", "bgp_asn": 65020},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"FP Tenant {n}", "code": f"FPT{n}", "type": "enterprise"},
    ).json()
    dev_a = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"FP-A-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.20.{n}.1",
            "loopback_ip": f"10.255.{n}.1",
            "bgp_asn": 65020,
            "site_id": site["id"],
        },
    ).json()
    dev_z = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"FP-Z-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.20.{n}.2",
            "loopback_ip": f"10.255.{n}.2",
            "bgp_asn": 65020,
            "site_id": site["id"],
        },
    ).json()
    client.post(
        "/api/v1/capacity/links",
        headers=auth_headers,
        json={
            "name": f"FP-LINK-{n}",
            "type": "dci",
            "device_a_id": dev_a["id"],
            "device_z_id": dev_z["id"],
            "interface_a": "GE1/0/49",
            "interface_z": "GE1/0/49",
            "capacity_mbps": 10000,
        },
    )
    cr = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": f"FP Circuit {n}",
            "tenant_id": tenant["id"],
            "service_type": "l2vpn_evpn",
            "bandwidth_mbps": 500,
            "endpoints": [
                {"label": "A", "device_id": dev_a["id"], "interface_name": "GE1/0/10"},
                {"label": "Z", "device_id": dev_z["id"], "interface_name": "GE1/0/10"},
            ],
        },
    )
    assert cr.status_code == 201, cr.text
    circuit = cr.json()
    client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    return circuit, dev_a, dev_z


def test_forwarding_path_api(client, auth_headers):
    circuit, dev_a, dev_z = _bootstrap_path_topology(client, auth_headers)

    r = client.get(
        f"/api/v1/circuits/{circuit['id']}/forwarding-path",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()

    assert body["circuit_id"] == circuit["id"]
    assert body["business_plane"]["vni"] == circuit["vni"]
    assert body["business_plane"]["topology"] == "point_to_point"
    assert len(body["business_plane"]["hops"]) >= 3

    assert "control_plane" in body
    assert body["control_plane"]["source"] == "controller_rib"
    assert isinstance(body["control_plane"]["routes"], list)

    underlay = body["underlay"]
    assert underlay["computed"]["device_ids"] == [dev_a["id"], dev_z["id"]]
    assert len(underlay["computed"]["segments"]) == 1
    assert underlay["topology_highlight"]["device_ids"] == [dev_a["id"], dev_z["id"]]
    assert underlay["comparison"]["status"] in ("no_probe", "match", "partial", "mismatch")

    path = client.get(
        f"/api/v1/circuits/{circuit['id']}/path",
        headers=auth_headers,
    ).json()
    assert path["igp_algorithm"] in ("dijkstra_igp_cost", "bfs_hop_count", "explicit_sr")
    assert "segments" in path


def test_forwarding_path_after_probe(client, auth_headers):
    circuit, _, _ = _bootstrap_path_topology(client, auth_headers)
    probe = client.post(
        f"/api/v1/circuits/{circuit['id']}/probe",
        headers=auth_headers,
    )
    assert probe.status_code == 200

    body = client.get(
        f"/api/v1/circuits/{circuit['id']}/forwarding-path",
        headers=auth_headers,
    ).json()
    assert body["underlay"]["probed"]["available"] is True
    assert body["underlay"]["comparison"]["status"] in ("match", "partial", "mismatch")
