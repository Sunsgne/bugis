"""Rendered H3C/Huawei config shows commit/save; the push strips them.

The transport layer (netmiko commit / save_config, H3C save RPC) owns
commit/save, but the *displayed* config must show them so operators see the
persistence steps (the recurring "还缺个保存" feedback).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.drivers.config_text import to_command_list
from app.drivers.registry import get_driver
from app.models.enums import AccessMode, Vendor


def _ctx():
    tenant = SimpleNamespace(name="Acme", code="ACME")
    circuit = SimpleNamespace(
        code="CIR-A9F89E", name="line", vni=30000, vlan_id=1111, mtu=9000,
        bandwidth_mbps=200, tenant=tenant, tenant_id=4,
        route_distinguisher="65001:30000", route_target="65001:30000",
        vsi_name="vsi_cir_a9f89e", vrf_name="vrf_cir_a9f89e",
        service_type=SimpleNamespace(value="l2vpn_evpn"),
    )
    endpoint = SimpleNamespace(
        access_mode=AccessMode.DOT1Q, vlan_id=1111, inner_vlan_id=None,
        interface_name="10GE1/0/14",
        gateway_ip="192.168.10.1", ip_address="192.168.10.2", prefix_len=24,
    )
    device = SimpleNamespace(name="cs-1.tyo1", loopback_ip="10.1.1.1", bgp_asn=65001)
    return {"circuit": circuit, "endpoint": endpoint, "device": device,
            "site": None, "partial": False}


@pytest.mark.parametrize("op", ["apply", "remove"])
def test_huawei_render_shows_commit_and_save(op):
    cfg = get_driver(Vendor.HUAWEI).render("l2vpn_evpn", op, _ctx())
    stripped = [ln.strip() for ln in cfg.splitlines()]
    # Displayed config shows the two-stage persistence: commit -> return -> save -> Y.
    assert "commit" in stripped, cfg
    assert "return" in stripped, cfg
    assert "save" in stripped, cfg
    assert any("confirm save" in ln.lower() and "y" in ln.lower() for ln in stripped), cfg
    assert stripped.index("commit") < stripped.index("return") < stripped.index("save")
    # ...but they are NOT pushed as plain config commands (transport owns them).
    cmds = [c.strip().lower() for c in to_command_list(Vendor.HUAWEI, cfg)]
    assert "commit" not in cmds
    assert "save" not in cmds
    assert "return" not in cmds


@pytest.mark.parametrize("op", ["apply", "remove"])
def test_h3c_render_shows_save_force(op):
    cfg = get_driver(Vendor.H3C).render("l2vpn_evpn", op, _ctx())
    stripped = [ln.strip() for ln in cfg.splitlines()]
    assert "save force" in stripped, cfg
    cmds = [c.strip().lower() for c in to_command_list(Vendor.H3C, cfg)]
    assert "save force" not in cmds
    assert "save" not in cmds
    assert "return" not in cmds
