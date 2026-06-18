"""Health snapshot + Redis cache integration tests."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.circuit import Circuit
from app.models.enums import CircuitStatus, ServiceType
from app.models.health_snapshot import CircuitHealthSnapshot
from app.models.tenant import Tenant
from app.schemas.telemetry import CircuitHealth
from app.services import health_snapshot_service


@pytest.fixture
def db_session():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _circuit(db_session) -> Circuit:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(name=f"HS {suffix}", code=f"HS{suffix}")
    db_session.add(tenant)
    db_session.flush()
    circuit = Circuit(
        name="Health Snap",
        code=f"HS-{suffix}",
        tenant_id=tenant.id,
        service_type=ServiceType.L2VPN_EVPN,
        status=CircuitStatus.ACTIVE,
        bandwidth_mbps=100,
    )
    db_session.add(circuit)
    db_session.commit()
    return circuit


def test_upsert_and_tenant_avg(db_session):
    circuit = _circuit(db_session)
    health = CircuitHealth(
        circuit_id=circuit.id,
        circuit_code=circuit.code,
        status="active",
        bandwidth_mbps=100,
        samples=10,
        qos_samples=2,
        avg_latency_ms=12.0,
        avg_utilization_pct=30.0,
        peak_utilization_pct=45.0,
        health_score=88.5,
    )
    health_snapshot_service.upsert_from_health(db_session, circuit.id, health)
    db_session.commit()

    snap = db_session.get(CircuitHealthSnapshot, circuit.id)
    assert snap is not None
    assert snap.health_score == 88.5
    assert snap.samples == 10

    avg, count = health_snapshot_service.tenant_monitorable_stats(
        db_session, circuit.tenant_id
    )
    assert count == 1
    assert avg == 88.5


def test_snapshot_to_health_roundtrip(db_session):
    circuit = _circuit(db_session)
    health_snapshot_service.upsert_from_health(
        db_session,
        circuit.id,
        CircuitHealth(
            circuit_id=circuit.id,
            circuit_code=circuit.code,
            status="active",
            bandwidth_mbps=100,
            samples=3,
            health_score=91.0,
            tunnel_down=True,
        ),
    )
    db_session.commit()
    out = health_snapshot_service.get_snapshot_health(db_session, circuit)
    assert out is not None
    assert out.health_score == 91.0
    assert out.tunnel_down is True


def test_redis_cache_graceful_when_disabled():
    from app.core import redis_client

    with patch("app.core.redis_client.redis_enabled", return_value=False):
        assert redis_client.cache_get_json("any") is None
        redis_client.cache_set_json("any", {"x": 1}, 30)
        redis_client.cache_delete("any")
