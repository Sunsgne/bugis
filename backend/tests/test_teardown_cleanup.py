"""Circuit teardown must fully scrub vendor config (no dirty VSI/QoS left).

Covers two regressions:
  * H3C remove templates issued ``undo qos apply policy`` in *interface* view
    (it was applied inside the service-instance). On H3C that command errors and
    aborts the atomic NETCONF <CLI> block, leaving VSI / QoS policy / behavior
    behind. The teardown now relies on ``undo service-instance`` and only emits
    valid commands.
  * H3C/Huawei destructive ``undo`` commands raise a "Continue? [Y/N]" prompt
    that the CLI push must auto-confirm, otherwise the rest of the teardown is
    swallowed by the prompt.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.drivers.config_text import to_command_list
from app.drivers.registry import get_driver
from app.models.enums import AccessMode, Vendor


def _ctx():
    tenant = SimpleNamespace(name="Acme Bank", code="ACME")
    circuit = SimpleNamespace(
        code="CIR-03BE2D", name="line", vni=30001, vlan_id=1234, mtu=9000,
        bandwidth_mbps=999, tenant=tenant, tenant_id=4,
        route_distinguisher="65001:30001", route_target="65001:30001",
        vsi_name="vsi_cir_03be2d", vrf_name="vrf_cir_03be2d",
        service_type=SimpleNamespace(value="l2vpn_evpn"),
    )
    endpoint = SimpleNamespace(
        access_mode=AccessMode.DOT1Q, vlan_id=1234, inner_vlan_id=None,
        interface_name="Ten-GigabitEthernet1/0/14",
        gateway_ip="192.168.10.1", ip_address="192.168.10.2", prefix_len=24,
    )
    device = SimpleNamespace(name="cs-1.tyo1", loopback_ip="10.1.1.1", bgp_asn=65001)
    return {"circuit": circuit, "endpoint": endpoint, "device": device,
            "site": None, "partial": False}


@pytest.mark.parametrize("service", ["l2vpn_evpn", "l3vpn_evpn", "remote_ipt"])
def test_h3c_remove_scrubs_qos_and_vsi(service):
    cfg = get_driver(Vendor.H3C).render(service, "remove", _ctx())
    cmds = to_command_list(Vendor.H3C, cfg)
    # The wrong-view command that aborted the atomic teardown must be gone.
    assert not any("undo qos apply policy" in c for c in cmds), cmds
    # The global objects that used to leak must be explicitly removed.
    assert any(c.startswith("undo qos policy") for c in cmds), cmds
    assert any(c.startswith("undo traffic behavior") for c in cmds), cmds
    assert any(c.startswith("undo traffic classifier") for c in cmds), cmds
    assert any(c.startswith("undo vsi") for c in cmds), cmds
    # The system-scoped undo commands must be issued AFTER a quit returns to
    # system-view (the interface block leaves us in interface view otherwise).
    stripped = [c.strip() for c in cmds]
    assert "quit" in stripped, cmds
    assert stripped.index("quit") < next(
        i for i, c in enumerate(stripped) if c.startswith("undo vsi")
    ), cmds


@pytest.mark.parametrize("service", ["l2vpn_evpn", "l3vpn_evpn"])
def test_huawei_remove_quit_before_bridge_domain(service):
    cfg = get_driver(Vendor.HUAWEI).render(service, "remove", _ctx())
    stripped = [c.strip() for c in to_command_list(Vendor.HUAWEI, cfg)]
    # interface Nve1 ... undo vni ... quit ... undo bridge-domain
    assert "quit" in stripped, stripped
    nve = stripped.index("interface Nve1")
    bd = next(i for i, c in enumerate(stripped) if c.startswith("undo bridge-domain"))
    quit_idx = next(i for i in range(nve, bd) if stripped[i] == "quit")
    assert nve < quit_idx < bd, stripped


@pytest.mark.parametrize("service", ["l2vpn_evpn", "l3vpn_evpn"])
def test_huawei_remove_scrubs_qos_and_bridge_domain(service):
    cfg = get_driver(Vendor.HUAWEI).render(service, "remove", _ctx())
    cmds = to_command_list(Vendor.HUAWEI, cfg)
    assert any(c.startswith("undo traffic policy") for c in cmds), cmds
    assert any(c.startswith("undo traffic behavior") for c in cmds), cmds
    # The shared 'ANY' classifier is reused by every circuit's traffic-policy, so
    # a single circuit teardown must NOT remove it.
    assert not any(c.startswith("undo traffic classifier") for c in cmds), cmds
    assert any(c.startswith("undo bridge-domain") for c in cmds), cmds


class _FakeConn:
    """Minimal netmiko-like connection that confirms one destructive command."""

    def __init__(self, prompt_on: set[str]):
        self.prompt_on = prompt_on
        self.sent: list[str] = []
        self.in_config = False

    def config_mode(self):
        self.in_config = True

    def exit_config_mode(self):
        self.in_config = False

    def send_command_timing(self, cmd, read_timeout=120):
        self.sent.append(cmd)
        if cmd in self.prompt_on:
            return "Warning: This operation will delete the VSI. Continue? [Y/N]:"
        return ""

    def send_config_set(self, *args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("H3C/Huawei must use the per-command confirm path")


def test_cli_push_auto_confirms_destructive_undo():
    driver = get_driver(Vendor.HUAWEI)
    conn = _FakeConn(prompt_on={"undo bridge-domain 30001"})
    driver._send_config_commands(
        conn, ["undo interface 10GE1/0/14.1234", "undo bridge-domain 30001"], 120
    )
    # A 'Y' confirmation was injected right after the prompting command.
    assert conn.sent == [
        "undo interface 10GE1/0/14.1234",
        "undo bridge-domain 30001",
        "Y",
    ]
    assert conn.in_config is True  # VRP8: stay in config mode until commit()


class _HuaweiTeardownConn(_FakeConn):
    """Track whether exit_config_mode runs before an external commit()."""

    def __init__(self):
        super().__init__(prompt_on=set())
        self.exit_before_commit = False
        self.committed = False

    def exit_config_mode(self, *args, **kwargs):
        if not self.committed:
            self.exit_before_commit = True
        self.in_config = False
        return ""

    def commit(self, **kwargs):
        self.committed = True
        return "commit complete"


def test_huawei_teardown_defers_exit_until_commit():
    """VRP8 teardown must not return to user view before commit()."""
    driver = get_driver(Vendor.HUAWEI)
    conn = _HuaweiTeardownConn()
    driver._send_config_commands(conn, ["undo bridge-domain 30001"], 120)
    assert conn.exit_before_commit is False
    driver._commit_if_needed(conn)
    assert conn.committed is True


class _BatchConn:
    def __init__(self):
        self.batched = None

    def send_config_set(self, commands, **kwargs):
        self.batched = list(commands)
        return "ok"


def test_cli_push_keeps_batched_send_for_other_vendors():
    driver = get_driver(Vendor.CISCO)
    conn = _BatchConn()
    out = driver._send_config_commands(conn, ["a", "b"], 120)
    assert conn.batched == ["a", "b"]
    assert out == "ok"
