"""Auto-rollback: when a circuit push partially fails, already-applied config on
the healthy devices is rolled back."""
from __future__ import annotations

import itertools

import pytest

_seq = itertools.count(9000)


def _bootstrap(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": f"RB DC {n}", "code": f"RB-DC{n}", "bgp_asn": 65030},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": f"RB Tenant {n}", "code": f"RB-TEN{n}", "type": "enterprise"},
    ).json()
    dev_a = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"RB-H3C-{n}", "vendor": "h3c", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": f"10.30.{n % 250}.1", "bgp_asn": 65030, "site_id": site["id"]},
    ).json()
    dev_z = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": f"RB-CSCO-{n}", "vendor": "cisco", "role": "pe",
              "overlay_tech": "srmpls_evpn", "status": "online",
              "mgmt_ip": f"10.30.{n % 250}.2", "bgp_asn": 65030, "site_id": site["id"]},
    ).json()
    return tenant, dev_a, dev_z


def _make_circuit(client, auth_headers, tenant, dev_a, dev_z, name):
    n = next(_seq)
    svid = 2000 + (n % 1500)
    return client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": name, "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 200,
              "endpoints": [
                  {"label": "A", "device_id": dev_a["id"],
                   "interface_name": f"GE1/0/{n % 40 + 2}", "vlan_id": svid},
                  {"label": "Z", "device_id": dev_z["id"],
                   "interface_name": f"GE1/0/{n % 40 + 2}", "vlan_id": svid},
              ]},
    ).json()


def _patch_push(monkeypatch, fail_device_id, calls):
    from app.drivers.base import BaseDriver, DriverResult

    orig = BaseDriver.push

    def fake_push(self, device, config, dry_run=True):
        calls.append((device.id, config))
        if device.id == fail_device_id:
            return DriverResult(
                success=False, config=config,
                output="forced failure for test", dry_run=dry_run,
            )
        return orig(self, device, config, dry_run=dry_run)

    monkeypatch.setattr(BaseDriver, "push", fake_push)


def test_partial_failure_rolls_back_healthy_device(client, auth_headers, monkeypatch):
    tenant, dev_a, dev_z = _bootstrap(client, auth_headers)
    circuit = _make_circuit(client, auth_headers, tenant, dev_a, dev_z, "RB E2E")

    calls: list[tuple[int, str]] = []
    _patch_push(monkeypatch, fail_device_id=dev_z["id"], calls=calls)

    prov = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert prov.status_code == 201, prov.text
    body = prov.json()

    # Work order failed, circuit failed.
    assert body["status"] == "failed"
    assert body["circuit_status"] == "failed"

    # Healthy device (dev_a) was pushed twice: the apply AND the rollback.
    a_pushes = [c for c in calls if c[0] == dev_a["id"]]
    z_pushes = [c for c in calls if c[0] == dev_z["id"]]
    assert len(a_pushes) == 2, calls
    # Failed device is ALSO scrubbed (best-effort cleanup of half-applied config):
    # apply attempt + remove cleanup.
    assert len(z_pushes) == 2, calls
    # The 2nd push to dev_a is the inverse (remove/undo) config.
    assert "undo" in a_pushes[1][1].lower()

    # Rollback was recorded in the work order timeline.
    wo = client.get(
        f"/api/v1/work-orders/{body['id']}", headers=auth_headers
    ).json()
    messages = " | ".join(e["message"] for e in wo["events"])
    assert "回滚" in messages
    assert "已回滚" in messages
    # The failed device's residual config was cleaned up too.
    assert "清理残留" in messages


def test_full_success_does_not_roll_back(client, auth_headers, monkeypatch):
    tenant, dev_a, dev_z = _bootstrap(client, auth_headers)
    circuit = _make_circuit(client, auth_headers, tenant, dev_a, dev_z, "RB OK")

    calls: list[tuple[int, str]] = []
    _patch_push(monkeypatch, fail_device_id=-1, calls=calls)  # nothing fails

    prov = client.post(
        f"/api/v1/work-orders/provision/{circuit['id']}", headers=auth_headers
    )
    assert prov.status_code == 201, prov.text
    body = prov.json()
    assert body["status"] == "completed"
    assert body["circuit_status"] == "active"

    # Each device pushed exactly once (apply only, no rollback).
    assert len([c for c in calls if c[0] == dev_a["id"]]) == 1
    assert len([c for c in calls if c[0] == dev_z["id"]]) == 1

    wo = client.get(
        f"/api/v1/work-orders/{body['id']}", headers=auth_headers
    ).json()
    messages = " | ".join(e["message"] for e in wo["events"])
    assert "回滚" not in messages
