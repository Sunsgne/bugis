"""Tests for parallel config learning."""
from __future__ import annotations

import itertools

from app.core.database import SessionLocal
from app.models.device import Device
from app.models.enums import Vendor
from app.services import concurrent_learn

_seq = itertools.count(1)


def test_learn_devices_parallel_runs_all():
    db = SessionLocal()
    try:
        ids: list[int] = []
        for _ in range(3):
            n = next(_seq)
            dev = Device(name=f"LEARN-PAR-{n}", vendor=Vendor.H3C, mgmt_ip=f"10.77.{n}.1")
            db.add(dev)
            db.flush()
            ids.append(dev.id)
        db.commit()

        summary = concurrent_learn.learn_devices_parallel(
            ids,
            created_by="test",
            discover_snmp=False,
            max_workers=3,
        )
        assert summary["total"] == 3
        assert summary["max_workers"] == 3
        assert len(summary["results"]) == 3
    finally:
        db.close()


def test_learn_batch_api(client, auth_headers):
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": "Learn Batch DC", "code": "LBDC", "bgp_asn": 65001},
    ).json()
    ids = []
    for i in range(2):
        dev = client.post(
            "/api/v1/devices",
            headers=auth_headers,
            json={
                "name": f"LB-DEV-{i}",
                "vendor": "h3c",
                "role": "leaf",
                "overlay_tech": "vxlan_evpn",
                "status": "online",
                "mgmt_ip": f"10.78.0.{i + 1}",
                "site_id": site["id"],
            },
            params={"learn": False},
        ).json()
        ids.append(dev["id"])

    r = client.post(
        "/api/v1/devices/learn-batch",
        headers=auth_headers,
        json={"device_ids": ids, "max_workers": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["max_workers"] == 2
    assert len(body["results"]) == 2
