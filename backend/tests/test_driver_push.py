"""Tests for real CLI / NETCONF push behavior (fake transports, no live gear)."""
from __future__ import annotations

import sys
import types

import pytest

from app.drivers.registry import get_driver
from app.models.enums import ManagementTransport, Vendor


class FakeDevice:
    def __init__(self, vendor: Vendor, transport=ManagementTransport.AUTO):
        self.vendor = vendor
        self.management_transport = transport
        self.active_mgmt_ip = "10.0.0.1"
        self.mgmt_ip = "10.0.0.1"
        self.name = "cs-1.eqty8-2f-000010-row1-108-u14.tyo1"
        self.username = "admin"
        self.password = "secret"
        self.enable_password = None
        self.ssh_port = 22
        self.netconf_port = 830
        self.netmiko_device_type = None


class FakeConn:
    """Captures netmiko interactions."""

    instances: list["FakeConn"] = []

    def __init__(self, **params):
        self.params = params
        self.sent_commands = None
        self.send_config_kwargs = None
        self.paging_cmds: list[str] = []
        self.disconnected = False
        self.committed = False
        self.saved = False
        FakeConn.instances.append(self)

    def send_command(self, cmd, **kwargs):
        self.paging_cmds.append(cmd)
        return ""

    def send_config_set(self, commands, **kwargs):
        self.sent_commands = list(commands)
        self.send_config_kwargs = kwargs
        return "OK: applied %d command(s)" % len(self.sent_commands)

    def commit(self, **kwargs):
        self.committed = True
        return "commit complete"

    def save_config(self, **kwargs):
        self.saved = True
        return "save complete"

    def disconnect(self):
        self.disconnected = True


@pytest.fixture()
def fake_netmiko(monkeypatch):
    FakeConn.instances = []
    mod = types.ModuleType("netmiko")
    mod.ConnectHandler = FakeConn  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "netmiko", mod)
    return FakeConn


HUAWEI_CFG = """\
#
# Huawei VRP (Datacom) - EVPN VXLAN L2VPN  circuit=CIR-1 vni=30002
# device=cs-1.eqty8-2f-000010-row1-108-u14.tyo1
#
bridge-domain 30002
 vxlan vni 30002
#
interface 10GE1/0/11.1234 mode l2
 encapsulation dot1q vid 1234
 bridge-domain 30002
#
return
"""

H3C_CFG = """\
#
# H3C Comware7 - EVPN VXLAN L2VPN
#
l2vpn enable
#
vsi vsi_CIR-1
 vxlan 10100
#
return
"""


def test_push_cli_sanitizes_and_sets_cmd_verify(fake_netmiko):
    driver = get_driver(Vendor.HUAWEI)
    device = FakeDevice(Vendor.HUAWEI, transport=ManagementTransport.SSH)
    out = driver._push_cli(device, HUAWEI_CFG)

    conn = fake_netmiko.instances[-1]
    assert conn.disconnected is True
    # Huawei CE/datacom uses the two-stage VRP8 driver and must commit.
    assert conn.params.get("device_type") == "huawei_vrpv8"
    assert conn.committed is True
    # commit only writes the running datastore; the config must also be saved
    # to startup so it survives a reboot.
    assert conn.saved is True
    # Paging disabled for Huawei.
    assert any("screen-length" in c for c in conn.paging_cmds)
    # cmd_verify must be disabled (the production fix).
    assert conn.send_config_kwargs.get("cmd_verify") is False
    assert conn.send_config_kwargs.get("read_timeout")
    # Sanitized commands: no banners, no separators, no trailing return.
    assert all(not c.lstrip().startswith("#") for c in conn.sent_commands)
    assert "return" not in [c.strip().lower() for c in conn.sent_commands]
    assert "bridge-domain 30002" in conn.sent_commands
    assert " encapsulation dot1q vid 1234" in conn.sent_commands
    assert "OK:" in out


def test_push_cli_h3c_does_not_commit(fake_netmiko):
    driver = get_driver(Vendor.H3C)
    device = FakeDevice(Vendor.H3C, transport=ManagementTransport.SSH)
    driver._push_cli(device, H3C_CFG)
    conn = fake_netmiko.instances[-1]
    assert conn.params.get("device_type") == "hp_comware"
    assert conn.committed is False  # Comware is single-stage; no commit
    # Single-stage still only changes the running config, so it must be saved
    # to startup (Comware ``save force``) to persist across reboots.
    assert conn.saved is True


def test_push_cli_noop_when_nothing_to_push(fake_netmiko):
    driver = get_driver(Vendor.HUAWEI)
    device = FakeDevice(Vendor.HUAWEI, transport=ManagementTransport.SSH)
    out = driver._push_cli(device, "#\n# only comments\nreturn\n")
    assert "no-op" in out
    # No connection should have been opened.
    assert fake_netmiko.instances == []


def test_push_netconf_huawei_cli_text_raises(monkeypatch):
    # ncclient must be importable for _push_netconf to reach the vendor check.
    fake_ncclient = types.ModuleType("ncclient")
    fake_ncclient.manager = types.SimpleNamespace(connect=lambda **k: None)
    monkeypatch.setitem(sys.modules, "ncclient", fake_ncclient)

    driver = get_driver(Vendor.HUAWEI)
    device = FakeDevice(Vendor.HUAWEI)
    with pytest.raises(RuntimeError, match="CLI transport"):
        driver._push_netconf(device, HUAWEI_CFG)


def test_push_netconf_h3c_wraps_cli_rpc(monkeypatch):
    captured = {}

    class FakeMgr:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def dispatch(self, ele):
            captured.setdefault("dispatched", []).append(ele)
            return "<ok/>"

        def edit_config(self, **kwargs):
            captured["edit_config"] = kwargs
            return "<ok/>"

    fake_ncclient = types.ModuleType("ncclient")
    fake_ncclient.manager = types.SimpleNamespace(connect=lambda **k: FakeMgr())
    monkeypatch.setitem(sys.modules, "ncclient", fake_ncclient)

    fake_xml = types.ModuleType("ncclient.xml_")
    fake_xml.to_ele = lambda s: s  # passthrough returns the xml string
    monkeypatch.setitem(sys.modules, "ncclient.xml_", fake_xml)

    driver = get_driver(Vendor.H3C)
    device = FakeDevice(Vendor.H3C)
    out = driver._push_netconf(device, H3C_CFG)

    dispatched = captured["dispatched"]
    rpc = dispatched[0]
    assert "<Configuration>" in rpc
    assert "l2vpn enable" in rpc
    assert "vsi vsi_CIR-1" in rpc
    # No banner / trailing return inside the RPC payload.
    assert "# H3C" not in rpc
    assert "return" not in rpc
    assert "edit_config" not in captured
    assert "<ok/>" in out
    # A second RPC must persist the config to startup (save force) via the
    # user-view Execution element; otherwise the apply is lost on reboot.
    save_rpc = dispatched[1]
    assert "<Execution>save force</Execution>" in save_rpc


def test_push_netconf_xml_passthrough(monkeypatch):
    captured = {}

    class FakeMgr:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def edit_config(self, **kwargs):
            captured["edit_config"] = kwargs
            return "<ok/>"

    fake_ncclient = types.ModuleType("ncclient")
    fake_ncclient.manager = types.SimpleNamespace(connect=lambda **k: FakeMgr())
    monkeypatch.setitem(sys.modules, "ncclient", fake_ncclient)

    driver = get_driver(Vendor.HUAWEI)
    device = FakeDevice(Vendor.HUAWEI)
    xml = "<config><top/></config>"
    out = driver._push_netconf(device, xml)
    assert captured["edit_config"]["config"] == xml
    # Always merge into running — never replace — to protect unmanaged live config.
    assert captured["edit_config"].get("default_operation") == "merge"
    assert captured["edit_config"].get("target") == "running"
    assert "<ok/>" in out


def test_real_push_falls_back_netconf_to_cli(monkeypatch, fake_netmiko):
    # ncclient importable; Huawei CLI text over NETCONF raises -> fallback to CLI.
    fake_ncclient = types.ModuleType("ncclient")
    fake_ncclient.manager = types.SimpleNamespace(connect=lambda **k: None)
    monkeypatch.setitem(sys.modules, "ncclient", fake_ncclient)

    driver = get_driver(Vendor.HUAWEI)
    device = FakeDevice(Vendor.HUAWEI, transport=ManagementTransport.AUTO)
    # Primary transport resolves to netconf (Huawei driver default).
    out = driver._real_push(device, HUAWEI_CFG)
    # CLI fallback was used.
    assert fake_netmiko.instances, "expected CLI fallback to open a connection"
    assert "OK:" in out
