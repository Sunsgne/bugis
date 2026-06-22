"""Tenant portal — scoped access to own circuits, traffic and billing."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_circuit, require_tenant_user
from app.core.config import settings
from app.core.database import get_db
from app.core import redis_client
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.enums import AlarmStatus, CircuitStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.portal import (
    PortalCircuitListOut,
    PortalCircuitOut,
    PortalDashboardOut,
    PortalMeOut,
)
from app.schemas.tenant import TenantSummary
from app.services import health_snapshot_service, telemetry_service
from app.services.availability_service import compute_availability

router = APIRouter()


def _tenant_summary(db: Session, tenant_id: int) -> TenantSummary:
    from app.api.v1.tenants import _build_tenant_summary

    return _build_tenant_summary(db, tenant_id)


def _to_portal_list(circuit: Circuit) -> PortalCircuitListOut:
    return PortalCircuitListOut(
        id=circuit.id,
        code=circuit.code,
        name=circuit.name,
        service_type=circuit.service_type,
        status=circuit.status,
        bandwidth_mbps=circuit.bandwidth_mbps,
        vni=circuit.vni,
        vsi_name=circuit.vsi_name,
        sla_target=circuit.sla_target,
        latency_probe_enabled=circuit.latency_probe_enabled,
        endpoint_count=len(circuit.endpoints or []),
        created_at=circuit.created_at,
        updated_at=circuit.updated_at,
    )


@router.get("/me", response_model=PortalMeOut)
def portal_me(user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return PortalMeOut(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role.value,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_code=tenant.code,
    )


@router.get("/dashboard", response_model=PortalDashboardOut)
def portal_dashboard(
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    cache_key = health_snapshot_service.cache_key_portal_dashboard(user.tenant_id)
    cached = redis_client.cache_get_json(cache_key)
    if cached:
        return PortalDashboardOut(**cached)

    circuits = db.execute(
        select(Circuit).where(Circuit.tenant_id == user.tenant_id)
    ).scalars().all()
    circuit_ids = [c.id for c in circuits]
    active_alarms = 0
    if circuit_ids:
        active_alarms = int(
            db.scalar(
                select(func.count(Alarm.id)).where(
                    Alarm.circuit_id.in_(circuit_ids),
                    Alarm.status == AlarmStatus.ACTIVE,
                )
            )
            or 0
        )
    avg_health, monitorable = health_snapshot_service.tenant_monitorable_stats(
        db, user.tenant_id
    )
    result = PortalDashboardOut(
        summary=_tenant_summary(db, user.tenant_id),
        active_alarms=active_alarms,
        avg_health_score=avg_health,
        circuits_monitorable=monitorable,
    )
    redis_client.cache_set_json(
        cache_key,
        result.model_dump(mode="json"),
        settings.redis_portal_dashboard_ttl_seconds,
    )
    return result


@router.get("/circuits", response_model=list[PortalCircuitListOut])
def portal_list_circuits(
    status: CircuitStatus | None = None,
    q: str | None = None,
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Circuit)
        .where(Circuit.tenant_id == user.tenant_id)
        .order_by(Circuit.id.desc())
    )
    if status:
        stmt = stmt.where(Circuit.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (Circuit.code.ilike(like)) | (Circuit.name.ilike(like))
        )
    circuits = db.execute(stmt).scalars().all()
    return [_to_portal_list(c) for c in circuits]


@router.get("/circuits/{circuit_id}", response_model=PortalCircuitOut)
def portal_get_circuit(
    circuit_id: int,
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    circuit = get_tenant_circuit(db, user, circuit_id)
    base = _to_portal_list(circuit)
    return PortalCircuitOut(
        **base.model_dump(),
        description=circuit.description,
        endpoints=circuit.endpoints,
        path_mode=circuit.path_mode.value if circuit.path_mode else None,
    )


@router.get("/circuits/{circuit_id}/traffic-summary")
def portal_traffic_summary(
    circuit_id: int,
    limit: int = 5000,
    hours: int | None = 24,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    circuit = get_tenant_circuit(db, user, circuit_id)
    eff_hours = telemetry_service._window_hours(
        hours=hours, start_at=start_at, end_at=end_at
    )
    use_cache = start_at is None and end_at is None and eff_hours > settings.telemetry_aggregate_after_hours
    cache_key = health_snapshot_service.cache_key_traffic(circuit.id, eff_hours)
    if use_cache:
        cached = redis_client.cache_get_json(cache_key)
        if cached:
            return cached
    payload = telemetry_service.traffic_summary_payload(
        db,
        circuit,
        limit=limit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )
    if use_cache:
        serializable = dict(payload)
        serializable["samples"] = [
            s if isinstance(s, dict) else {
                "id": s.id,
                "circuit_id": s.circuit_id,
                "rx_mbps": s.rx_mbps,
                "tx_mbps": s.tx_mbps,
                "utilization_pct": s.utilization_pct,
                "latency_ms": s.latency_ms,
                "jitter_ms": s.jitter_ms,
                "packet_loss_pct": s.packet_loss_pct,
                "errors": s.errors,
                "tunnel_state": s.tunnel_state,
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in payload["samples"]
        ]
        serializable["qos_samples"] = [
            s if isinstance(s, dict) else {
                "id": s.id,
                "circuit_id": s.circuit_id,
                "rx_mbps": s.rx_mbps,
                "tx_mbps": s.tx_mbps,
                "latency_ms": s.latency_ms,
                "jitter_ms": s.jitter_ms,
                "packet_loss_pct": s.packet_loss_pct,
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in payload.get("qos_samples") or []
        ]
        redis_client.cache_set_json(
            cache_key,
            serializable,
            settings.redis_traffic_summary_ttl_seconds,
        )
        return serializable
    return payload


@router.get("/circuits/{circuit_id}/billing")
def portal_billing(
    circuit_id: int,
    period: str | None = None,
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    circuit = get_tenant_circuit(db, user, circuit_id)
    return telemetry_service.billing_95th(db, circuit, period)


@router.get("/circuits/{circuit_id}/availability")
def portal_availability(
    circuit_id: int,
    hours: int = 24,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    circuit = get_tenant_circuit(db, user, circuit_id)
    return compute_availability(
        db,
        circuit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/circuits/{circuit_id}/health")
def portal_health(
    circuit_id: int,
    limit: int = 5000,
    hours: int | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    user: User = Depends(require_tenant_user),
    db: Session = Depends(get_db),
):
    circuit = get_tenant_circuit(db, user, circuit_id)
    windowed = hours is not None or (start_at is not None and end_at is not None)
    if not windowed:
        cache_key = health_snapshot_service.cache_key_health(circuit.id)
        cached = redis_client.cache_get_json(cache_key)
        if cached:
            return cached
        snap_health = health_snapshot_service.get_snapshot_health(db, circuit)
        if snap_health is not None:
            data = snap_health.model_dump()
            redis_client.cache_set_json(
                cache_key, data, settings.redis_health_ttl_seconds
            )
            return snap_health
    health = telemetry_service.compute_health(
        db,
        circuit,
        limit=limit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )
    if not windowed:
        redis_client.cache_set_json(
            health_snapshot_service.cache_key_health(circuit.id),
            health.model_dump(),
            settings.redis_health_ttl_seconds,
        )
    return health
