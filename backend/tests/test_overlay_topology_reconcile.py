"""Controller overlay topology reconciliation via network-learning scan, and
controller-state cleanup when a failed circuit is deleted."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.controlplane import EvpnRoute, VtepPeer
from app.models.enums import VtepStatus
from tests.test_api import _bootstrap_topology

_seq = itertools.count(7000)


def _add_peer(device_id: int, name: str, vnis: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            VtepPeer(
                device_id=device_id,
                name=name,
                vtep_ip=f"10.99.{device_id % 250}.1",
                asn=65010,
                status=VtepStatus.UP,
                vnis=vnis,
            )
        )
        db.commit()
    finally:
        db.close()


def _peer_vnis(device_id: int) -> set[int]:
    db = SessionLocal()
    try:
        peer = (
            db.query(VtepPeer).filter(VtepPeer.device_id == device_id).one_or_none()
        )
        if not peer:
            return set()
        return {int(v) for v in peer.vnis.split(",") if v.strip().isdigit()}
    finally:
        db.close()


def test_scan_prunes_stale_topology(client, auth_headers):
    _, _, dev_a, _ = _bootstrap_topology(client, auth_headers)
    stale_a, stale_b = 35001 + next(_seq), 35001 + next(_seq)
    _add_peer(dev_a["id"], dev_a["name"], f"{stale_a},{stale_b}")

    # Sanity: edge/vni present before scan.
    assert _peer_vnis(dev_a["id"]) == {stale_a, stale_b}

    resp = client.post("/api/v1/controller/overlay-inventory/scan", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["topology_reconciled"] is True
    assert body["stale_vni_removed"] >= 2

    # Stale VNIs pruned -> topology no longer carries them.
    assert _peer_vnis(dev_a["id"]) == set()
    topo = client.get("/api/v1/controller/topology", headers=auth_headers).json()
    flat_vnis = {e["vni"] for e in topo["edges"]}
    assert stale_a not in flat_vnis and stale_b not in flat_vnis


def test_scan_keeps_active_circuit_vni(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    svid = 1200 + (n % 600)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "keep-vni", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_a["id"],
                   "interface_name": f"GE1/0/{n % 30 + 2}", "vlan_id": svid},
                  {"label": "Z", "device_id": dev_z["id"],
                   "interface_name": f"GE1/0/{n % 30 + 2}", "vlan_id": svid},
              ]},
    ).json()
    prov = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    ).json()
    assert prov["circuit_status"] == "active"
    vni = circuit["vni"]

    # Register a VTEP with the active circuit's VNI plus a stale one.
    stale = 36001 + next(_seq)
    _add_peer(dev_a["id"], dev_a["name"], f"{vni},{stale}")

    resp = client.post("/api/v1/controller/overlay-inventory/scan", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    remaining = _peer_vnis(dev_a["id"])
    assert vni in remaining, "active circuit VNI must be retained"
    assert stale not in remaining, "stale VNI must be pruned"


def test_delete_circuit_purges_controller_state(client, auth_headers):
    _, tenant, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    svid = 1800 + (n % 150)
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "purge-on-delete", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev_a["id"],
                   "interface_name": f"GE1/0/{n % 30 + 2}", "vlan_id": svid},
                  {"label": "Z", "device_id": dev_z["id"],
                   "interface_name": f"GE1/0/{n % 30 + 2}", "vlan_id": svid},
              ]},
    ).json()
    cid = circuit["id"]
    vni = circuit["vni"]

    # Install controller state directly (simulates controller-managed delivery).
    db = SessionLocal()
    try:
        from app.controller import controller as bugis_controller
        from app.models.circuit import Circuit

        c = db.get(Circuit, cid)
        bugis_controller.install_circuit(db, c, list(c.endpoints))
        db.commit()
    finally:
        db.close()

    assert vni in _peer_vnis(dev_a["id"])
    db = SessionLocal()
    try:
        assert db.query(EvpnRoute).filter(EvpnRoute.circuit_id == cid).count() > 0
    finally:
        db.close()

    # Circuit is still draft -> deletable. Delete should purge controller state.
    resp = client.delete(f"/api/v1/circuits/{cid}", headers=auth_headers)
    assert resp.status_code in (200, 204), resp.text

    assert vni not in _peer_vnis(dev_a["id"])
    assert vni not in _peer_vnis(dev_z["id"])
    db = SessionLocal()
    try:
        assert db.query(EvpnRoute).filter(EvpnRoute.circuit_id == cid).count() == 0
    finally:
        db.close()


def test_topology_lists_all_overlay_devices_without_vtep(client, auth_headers):
    """Overlay graph must show every vxlan/sr-mpls device, not only VTEP registry rows."""
    _, _, dev_a, dev_z = _bootstrap_topology(client, auth_headers)
    n = next(_seq)
    ip_suffix = n % 200 + 1
    extra = client.post(
        f"/api/v1/devices?learn=false",
        headers=auth_headers,
        json={
            "name": f"overlay-extra-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "status": "online",
            "mgmt_ip": f"10.20.{ip_suffix}.10",
            "loopback_ip": f"10.20.{ip_suffix}.1",
            "username": "admin",
            "password": "secret",
        },
    ).json()

    topo = client.get("/api/v1/controller/topology", headers=auth_headers).json()
    node_ids = {node["id"] for node in topo["nodes"]}
    assert dev_a["id"] in node_ids
    assert dev_z["id"] in node_ids
    assert extra["id"] in node_ids

    scan = client.post("/api/v1/controller/overlay-inventory/scan", headers=auth_headers)
    assert scan.status_code == 200, scan.text
    assert scan.json().get("peers_created", 0) >= 1

    vteps = client.get("/api/v1/controller/vteps", headers=auth_headers).json()
    assert any(v["device_id"] == extra["id"] for v in vteps)
