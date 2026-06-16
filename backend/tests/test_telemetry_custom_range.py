"""Integration tests for custom-range 5-min 95 billing."""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

_seq = itertools.count(1)


def test_custom_range_billing_uses_5min_buckets(client, auth_headers):
    n = next(_seq)
    site = client.post(
        "/api/v1/sites",
        headers=auth_headers,
        json={"name": f"Tel DC {n}", "code": f"TEL{n}", "bgp_asn": 65001},
    ).json()
    tenant = client.post(
        "/api/v1/tenants",
        headers=auth_headers,
        json={"name": f"Tel Tenant {n}", "code": f"TT{n}"},
    ).json()
    device = client.post(
        "/api/v1/devices",
        headers=auth_headers,
        json={
            "name": f"TEL-LEAF-{n}",
            "vendor": "h3c",
            "role": "leaf",
            "overlay_tech": "vxlan_evpn",
            "mgmt_ip": f"10.7.{n}.1",
            "site_id": site["id"],
        },
        params={"learn": False},
    ).json()
    circuit = client.post(
        "/api/v1/circuits",
        headers=auth_headers,
        json={
            "name": "Tel Circuit",
            "tenant_id": tenant["id"],
            "bandwidth_mbps": 1000,
            "endpoints": [
                {"label": "A", "device_id": device["id"], "interface_name": "GE1/0/1"},
            ],
        },
    ).json()
    base = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(24):
        client.post(
            "/api/v1/telemetry/samples",
            headers=auth_headers,
            json={
                "circuit_id": circuit["id"],
                "rx_mbps": 100 + i * 10,
                "tx_mbps": 200 + i * 10,
                "utilization_pct": 10,
                "latency_ms": 2,
                "jitter_ms": 0.2,
                "packet_loss_pct": 0,
            },
        )
    start = quote((base - timedelta(minutes=5)).isoformat())
    end = quote((datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    summary = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/traffic-summary"
        f"?start_at={start}&end_at={end}",
        headers=auth_headers,
    ).json()
    billing = client.get(
        f"/api/v1/telemetry/circuits/{circuit['id']}/billing"
        f"?start_at={start}&end_at={end}",
        headers=auth_headers,
    ).json()
    assert summary["granularity_minutes"] == 5
    assert summary["p95"]["bucket_count"] >= 1
    assert billing["granularity_minutes"] == 5
    assert billing["billable_95_mbps"] > 0
    assert billing["retention"] == "permanent"
