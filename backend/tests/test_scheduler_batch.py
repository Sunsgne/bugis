"""Scheduler batching for large circuit fleets."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.tenant import Tenant
from app.scheduler import _collect_circuit_batch, _probe_one_circuit, _tick, _tick_lock


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _make_circuits(db_session, count: int) -> list[Circuit]:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"Batch {suffix}", code=f"B{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuits = []
    for i in range(count):
        c = Circuit(
            name=f"C{i}",
            code=f"B-{suffix}-{i}",
            tenant_id=tenant.id,
            service_type=ServiceType.L2VPN_EVPN,
            status=CircuitStatus.ACTIVE,
            bandwidth_mbps=100,
            latency_probe_enabled=i % 2 == 0,
        )
        db_session.add(c)
        circuits.append(c)
    db_session.commit()
    return circuits


def test_collect_batch_respects_limit(db_session):
    from app.core.config import settings

    circuits = _make_circuits(db_session, 12)
    with patch.object(settings, "telemetry_collect_batch_size", 5), patch(
        "app.services.telemetry_service.collect_circuit_sample", return_value=True
    ) as mock_collect:
        count, touched = _collect_circuit_batch(db_session, circuits, interval_sec=20.0)
        assert count == 5
        assert len(touched) == 5
        assert mock_collect.call_count == 5


def test_probe_batch_respects_limit(db_session):
    from app.core.config import settings

    circuits = _make_circuits(db_session, 20)
    with patch.object(settings, "dry_run", False), patch.object(
        settings, "telemetry_probe_batch_size", 4
    ), patch("app.services.circuit_probe.runner.probe_circuit") as mock_probe:
        count, touched = _probe_one_circuit(db_session, circuits)
        assert count == 4
        assert len(touched) == 4
        assert mock_probe.call_count == 4


def test_tick_skips_when_previous_still_running():
    _tick_lock.acquire()
    try:
        assert _tick() == 0
    finally:
        _tick_lock.release()
