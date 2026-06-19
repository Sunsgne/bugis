"""Localized work order default titles."""
from __future__ import annotations

from app.models.enums import WorkOrderType
from app.services.work_order_titles import default_work_order_title


def test_default_title_zh():
    assert default_work_order_title(
        WorkOrderType.PROVISION, "CIR-ABC", locale="zh"
    ) == "开通专线 CIR-ABC"
    assert default_work_order_title(
        WorkOrderType.DECOMMISSION, "CIR-ABC", locale="zh-CN"
    ) == "拆除专线 CIR-ABC"


def test_default_title_en():
    assert default_work_order_title(
        WorkOrderType.PROVISION, "CIR-ABC", locale="en"
    ) == "Provision circuit CIR-ABC"
    assert default_work_order_title(
        WorkOrderType.MODIFY, "CIR-XYZ", locale="en-US"
    ) == "Modify circuit CIR-XYZ"


def test_provision_title_follows_user_locale(client, auth_headers):
    r = client.patch(
        "/api/v1/auth/profile",
        headers=auth_headers,
        json={"locale": "en"},
    )
    assert r.status_code == 200, r.text
    site = client.post(
        "/api/v1/sites", headers=auth_headers,
        json={"name": "TL DC", "code": "TL-DC", "bgp_asn": 65010},
    ).json()
    tenant = client.post(
        "/api/v1/tenants", headers=auth_headers,
        json={"name": "TL Tenant", "code": "TL-TEN", "type": "internal"},
    ).json()
    dev = client.post(
        "/api/v1/devices", headers=auth_headers,
        json={"name": "TL-H3C", "vendor": "h3c", "role": "leaf",
              "overlay_tech": "vxlan_evpn", "status": "online",
              "mgmt_ip": "10.32.0.1", "bgp_asn": 65010, "site_id": site["id"]},
    ).json()
    circuit = client.post(
        "/api/v1/circuits", headers=auth_headers,
        json={"name": "TL L2", "tenant_id": tenant["id"],
              "service_type": "l2vpn_evpn", "bandwidth_mbps": 100,
              "endpoints": [
                  {"label": "A", "device_id": dev["id"],
                   "interface_name": "GE1/0/50"}
              ]},
    ).json()
    wo = client.post(
        "/api/v1/work-orders",
        headers=auth_headers,
        json={"circuit_id": circuit["id"], "type": "provision"},
    ).json()
    assert wo["title"] == f"Provision circuit {circuit['code']}"

    r = client.patch(
        "/api/v1/auth/profile",
        headers=auth_headers,
        json={"locale": "zh"},
    )
    assert r.status_code == 200, r.text
    wo_zh = client.post(
        "/api/v1/work-orders",
        headers=auth_headers,
        json={"circuit_id": circuit["id"], "type": "modify"},
    ).json()
    assert wo_zh["title"] == f"变更专线 {circuit['code']}"
