"""Interface descriptions render as '<customer>:<circuit>' (not CUST_<id>_)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.drivers.registry import get_driver
from app.models.enums import AccessMode, Vendor


def _ctx(vendor: Vendor):
    tenant = SimpleNamespace(name="Acme Bank", code="ACME")
    circuit = SimpleNamespace(
        code="CIR-5AF450",
        name="Acme line",
        vni=30002,
        vlan_id=1234,
        mtu=9000,
        bandwidth_mbps=100,
        tenant=tenant,
        tenant_id=4,
        route_distinguisher="65001:30002",
        route_target="65001:30002",
        vsi_name="vsi_cir_5af450",
        vrf_name="vrf_cir",
        service_type=SimpleNamespace(value="l2vpn_evpn"),
    )
    endpoint = SimpleNamespace(
        access_mode=AccessMode.DOT1Q,
        vlan_id=1234,
        inner_vlan_id=None,
        interface_name="10GE1/0/11",
        gateway_ip=None,
        ip_address=None,
    )
    device = SimpleNamespace(name="cs-1.tyo1", loopback_ip="10.1.1.1", bgp_asn=65001)
    return {"circuit": circuit, "endpoint": endpoint, "device": device, "site": None}


@pytest.mark.parametrize("vendor", [Vendor.HUAWEI, Vendor.H3C, Vendor.CISCO, Vendor.FRR])
def test_description_uses_customer_and_circuit(vendor):
    driver = get_driver(vendor)
    cfg = driver.render("l2vpn_evpn", "apply", _ctx(vendor))
    assert "Acme Bank:CIR-5AF450" in cfg, cfg
    # The old numeric tenant-id form must be gone.
    assert "CUST_4_CIR-5AF450" not in cfg
