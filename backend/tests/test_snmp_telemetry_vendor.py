"""Vendor-aware traffic polling: H3C uses the HH3C-EVC private MIB per
service-instance; Huawei uses sub-interface IF-MIB counters."""
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
    snmp_telemetry._ifname_index_cache.clear()
    return polled, values


def test_h3c_polls_evc_private_mib(patched_snmp):
    polled, values = patched_snmp
    evc_in = "1.3.6.1.4.1.25506.2.106.1.4.1.2.10.120"
    evc_out = "1.3.6.1.4.1.25506.2.106.1.4.1.4.10.120"
    values[evc_in] = 1000
    values[evc_out] = 2000

    device = SimpleNamespace(id=1, vendor=Vendor.H3C)
    target = snmp_telemetry._PollTarget(ifindex=10, name="GE1/0/1")
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, target=target, interval_sec=30.0, srv_inst_id=120
    )
    assert result is not None
    assert evc_in in polled, polled
    assert evc_out in polled, polled
    assert not any(o.startswith("1.3.6.1.2.1.31.1.1.1.6") for o in polled)


def test_h3c_no_port_fallback_when_evc_empty(patched_snmp):
    polled, _values = patched_snmp
    device = SimpleNamespace(id=2, vendor=Vendor.H3C)
    target = snmp_telemetry._PollTarget(ifindex=10, name="GE1/0/1")
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, target=target, interval_sec=30.0, srv_inst_id=120
    )
    assert result is None
    assert any(o.startswith("1.3.6.1.4.1.25506.2.106.1.4.1.2") for o in polled)
    assert not any(o.startswith("1.3.6.1.2.1.31.1.1.1.6") for o in polled)


def test_huawei_polls_standard_ifmib(patched_snmp):
    polled, values = patched_snmp
    values["1.3.6.1.2.1.31.1.1.1.6.7"] = 100
    values["1.3.6.1.2.1.31.1.1.1.10.7"] = 200

    device = SimpleNamespace(id=3, vendor=Vendor.HUAWEI)
    target = snmp_telemetry._PollTarget(ifindex=7, name="10GE1/0/2.120")
    result = snmp_telemetry._poll_iface_counters(
        db=None, device=device, target=target, interval_sec=30.0, srv_inst_id=120
    )
    assert result is not None
    assert "1.3.6.1.2.1.31.1.1.1.6.7" in polled
    assert not any(o.startswith("1.3.6.1.4.1.25506") for o in polled)


def test_endpoints_for_traffic_poll_prefers_a():
    circuit = SimpleNamespace(
        endpoints=[
            SimpleNamespace(label="Z", device_id=2),
            SimpleNamespace(label="A", device_id=1),
            SimpleNamespace(label="C", device_id=3),
        ]
    )
    picked = snmp_telemetry.endpoints_for_traffic_poll(circuit)
    assert len(picked) == 1
    assert picked[0].label == "A"


def test_resolve_poll_target_huawei_subif(monkeypatch):
    device = SimpleNamespace(id=9, vendor=Vendor.HUAWEI)
    db = object()
    monkeypatch.setattr(
        snmp_telemetry,
        "_ifname_index_map",
        lambda _db, _dev: {"10GE1/0/25.3439": 88},
    )
    monkeypatch.setattr(snmp_telemetry, "_resolve_iface", lambda *a, **k: None)
    monkeypatch.setattr(
        snmp_telemetry,
        "_persist_ifindex",
        lambda _db, _did, name, idx: SimpleNamespace(ifindex=idx, name=name),
    )
    target = snmp_telemetry._resolve_poll_target(db, device, "10GE1/0/25", 3439)
    assert target is not None
    assert target.ifindex == 88
    assert target.name == "10GE1/0/25.3439"


def test_resolve_poll_target_huawei_skips_physical_without_subif(monkeypatch):
    device = SimpleNamespace(id=10, vendor=Vendor.HUAWEI)
    db = object()
    monkeypatch.setattr(snmp_telemetry, "_ifname_index_map", lambda _db, _dev: {})
    monkeypatch.setattr(snmp_telemetry, "_resolve_iface", lambda *a, **k: None)
    target = snmp_telemetry._resolve_poll_target(db, device, "10GE1/0/25", 3439)
    assert target is None
