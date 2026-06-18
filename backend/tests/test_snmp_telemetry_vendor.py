"""Vendor-aware traffic polling: H3C uses the HH3C-EVC private MIB per
service-instance; Huawei/others use standard IF-MIB HC counters."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.enums import Vendor
from app.services import snmp_telemetry


@pytest.fixture()
def patched_snmp(monkeypatch):
    """Make SNMP appear enabled and capture the OIDs that get polled."""
    cfg = SimpleNamespace(enabled=True, port=161, timeout_sec=2, retries=1)
    monkeypatch.setattr(snmp_telemetry.snmp_cfg, "get_or_create", lambda db: cfg)
    monkeypatch.setattr(
        snmp_telemetry.snmp_cfg, "effective_community", lambda db, device: "public"
    )
    monkeypatch.setattr(
        snmp_telemetry.snmp_device,
        "effective_snmp",
        lambda device, *a, **k: {"enabled": True, "port": 161, "version": "2c"},
    )

    polled: list[str] = []
    values = {}  # oid -> value

    def fake_get_oid(device, oid, cfg, community, *, port=None):
        polled.append(oid)
        return values.get(oid)

    monkeypatch.setattr(snmp_telemetry, "_get_oid", fake_get_oid)
    snmp_telemetry._counter_cache.clear()
    return polled, values


def test_h3c_polls_evc_private_mib(patched_snmp):
    polled, values = patched_snmp
    # Provide EVC counters so no fallback happens.
    evc_in = "1.3.6.1.4.1.25506.2.106.1.4.1.2.10.120"
    evc_out = "1.3.6.1.4.1.25506.2.106.1.4.1.4.10.120"
    values[evc_in] = 1000
    values[evc_out] = 2000

    device = SimpleNamespace(id=1, vendor=Vendor.H3C)
    iface = SimpleNamespace(ifindex=10)
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, iface=iface, interval_sec=30.0, srv_inst_id=120
    )
    assert result is not None
    assert evc_in in polled, polled
    assert evc_out in polled, polled
    # Must NOT have used the standard IF-MIB octet counters for H3C.
    assert not any(o.startswith("1.3.6.1.2.1.31.1.1.1.6") for o in polled)


def test_h3c_falls_back_to_ifmib_when_evc_empty(patched_snmp):
    polled, values = patched_snmp
    # EVC returns nothing -> fall back to IF-MIB HC counters.
    values["1.3.6.1.2.1.31.1.1.1.6.10"] = 5000  # ifHCInOctets.10
    values["1.3.6.1.2.1.31.1.1.1.10.10"] = 6000  # ifHCOutOctets.10

    device = SimpleNamespace(id=2, vendor=Vendor.H3C)
    iface = SimpleNamespace(ifindex=10)
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, iface=iface, interval_sec=30.0, srv_inst_id=120
    )
    assert result is not None
    # Tried EVC first, then fell back to standard IF-MIB.
    assert any(o.startswith("1.3.6.1.4.1.25506.2.106.1.4.1.2") for o in polled)
    assert "1.3.6.1.2.1.31.1.1.1.6.10" in polled


def test_huawei_polls_standard_ifmib(patched_snmp):
    polled, values = patched_snmp
    values["1.3.6.1.2.1.31.1.1.1.6.7"] = 100  # ifHCInOctets.7
    values["1.3.6.1.2.1.31.1.1.1.10.7"] = 200  # ifHCOutOctets.7

    device = SimpleNamespace(id=3, vendor=Vendor.HUAWEI)
    iface = SimpleNamespace(ifindex=7)
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, iface=iface, interval_sec=30.0, srv_inst_id=120
    )
    assert result is not None
    assert "1.3.6.1.2.1.31.1.1.1.6.7" in polled
    # Huawei must not touch the H3C private MIB.
    assert not any(o.startswith("1.3.6.1.4.1.25506") for o in polled)
