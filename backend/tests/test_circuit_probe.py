"""Unit tests for circuit probe parsers, stats, and orchestration."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.circuit import Circuit, CircuitEndpoint
from app.models.device import Device
from app.models.enums import CircuitStatus, ServiceType, Vendor
from app.models.tenant import Tenant
from app.services.circuit_probe.parsers import parse_h3c_remote_mac, parse_ping_output
from app.services.circuit_probe.simulate import simulate_probe
from app.services.circuit_probe.stats import jitter_from_rtts, packet_loss_pct, summarize_rtts


H3C_PING = """
Ping 10.0.0.2: 5 data bytes, press CTRL+C to break
Reply from 10.0.0.2: bytes=56 Sequence=1 ttl=255 time=1.234 ms
Reply from 10.0.0.2: bytes=56 Sequence=2 ttl=255 time=1.456 ms
Reply from 10.0.0.2: bytes=56 Sequence=3 ttl=255 time=1.389 ms
Reply from 10.0.0.2: bytes=56 Sequence=4 ttl=255 time=1.512 ms
Reply from 10.0.0.2: bytes=56 Sequence=5 ttl=255 time=1.401 ms

--- Ping statistics for 10.0.0.2 ---
5 packet(s) transmitted, 5 packet(s) received, 0.0% packet loss
round-trip min/avg/max = 1.234/1.398/1.512 ms
"""


H3C_MAC = """
MAC Address    VSI Name                        Link ID
0011-2233-4455 vsi_cus_001                     1
"""


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def sample_circuit(db_session):
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Probe Tenant {suffix}", code=f"PRB{suffix}")
    db_session.add(tenant)
    db_session.flush()

    dev_a = Device(
        name=f"H3C-A-{suffix}", vendor=Vendor.H3C, mgmt_ip=f"10.1.{suffix[:2]}.1", loopback_ip=f"10.1.{suffix[:2]}.1",
        username="admin", password="secret",
    )
    dev_z = Device(
        name=f"H3C-Z-{suffix}", vendor=Vendor.H3C, mgmt_ip=f"10.1.{suffix[:2]}.2", loopback_ip=f"10.1.{suffix[:2]}.2",
        username="admin", password="secret",
    )
    db_session.add_all([dev_a, dev_z])
    db_session.flush()

    circuit = Circuit(
        name="Probe Circuit",
        code=f"PRB-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        vni=30100 + int(suffix[:4], 16) % 10000,
        vsi_name=f"vsi_prb_{suffix}",
        bandwidth_mbps=100,
    )
    db_session.add(circuit)
    db_session.flush()
    db_session.add_all([
        CircuitEndpoint(circuit_id=circuit.id, device_id=dev_a.id, label="A", interface_name="GE1/0/1"),
        CircuitEndpoint(circuit_id=circuit.id, device_id=dev_z.id, label="Z", interface_name="GE1/0/1"),
    ])
    db_session.commit()
    db_session.refresh(circuit)
    return circuit


def test_parse_ping_output_extracts_rtts_and_loss():
    parsed = parse_ping_output(H3C_PING)
    assert len(parsed["rtts_ms"]) == 5
    assert parsed["sent"] == 5
    assert parsed["received"] == 5
    assert parsed["loss_pct"] == 0.0
    assert parsed["avg_ms"] == 1.398


def test_parse_h3c_remote_mac():
    assert parse_h3c_remote_mac(H3C_MAC) == "0011-2233-4455"


def test_packet_loss_pct_formula():
    assert packet_loss_pct(5, 4) == 20.0
    assert packet_loss_pct(0, 0) == 100.0


def test_jitter_from_consecutive_samples():
    rtts = [1.0, 1.5, 1.2, 1.8]
    assert jitter_from_rtts(rtts) == round((0.5 + 0.3 + 0.6) / 3, 2)


def test_summarize_rtts():
    stats = summarize_rtts([1.0, 2.0, 3.0])
    assert stats["min_ms"] == 1.0
    assert stats["max_ms"] == 3.0
    assert stats["avg_ms"] == 2.0


def test_simulate_probe_labeled(db_session, sample_circuit):
    result = simulate_probe(db_session, sample_circuit)
    assert result["mode"] == "simulated"
    assert result["probe_method"] == "simulated"
    assert result["hop_count"] == len(result["hops"])
    assert result["service_plane"]["method"] == "simulated"


@patch("app.services.circuit_probe.runner.settings")
@patch("app.services.circuit_probe.runner.probe_service_plane")
@patch("app.services.circuit_probe.runner.probe_fabric_hops")
@patch("app.services.circuit_probe.runner.resolve_underlay_path")
def test_live_probe_uses_service_plane_metrics(
    mock_path, mock_fabric, mock_service, mock_settings, db_session, sample_circuit
):
    from app.services.circuit_probe.runner import probe_circuit

    mock_settings.dry_run = False
    sample_circuit.status = CircuitStatus.ACTIVE

    dev_a = MagicMock(name="A", mgmt_ip="10.0.0.1", loopback_ip="10.0.0.1")
    dev_a.name = "LEAF-A"
    dev_z = MagicMock(name="Z", mgmt_ip="10.0.0.2", loopback_ip="10.0.0.2")
    dev_z.name = "LEAF-Z"

    mock_path.return_value = {
        "devices": [dev_a, dev_z],
        "path_mode": "auto",
        "path_reason": "IGP shortest path",
        "segment_list": [],
        "hops_meta": [],
    }
    mock_fabric.return_value = (
        [{"hop": 1, "device": "LEAF-A", "status": "up", "rtt_ms": 2.0, "packet_loss_pct": 0.0}],
        {"method": "fabric_loopback", "reachable": True, "samples_per_hop": 5},
    )
    mock_service.return_value = {
        "method": "h3c_vsi_mac",
        "reachable": True,
        "rtts_ms": [3.0, 3.2, 3.1],
        "packet_loss_pct": 0.0,
        "jitter_ms": 0.15,
        "samples": 3,
    }

    with patch("app.services.circuit_probe.runner._ordered_endpoints", return_value=(dev_a, dev_z)):
        with patch("app.services.circuit_probe.runner._record_sample"):
            result = probe_circuit(db_session, sample_circuit)

    assert result["mode"] == "live"
    assert result["probe_method"] == "h3c_vsi_mac"
    assert result["rtt_ms"] == 3.1
    assert result["jitter_ms"] == jitter_from_rtts([3.0, 3.2, 3.1])
