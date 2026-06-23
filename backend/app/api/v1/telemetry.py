"""Telemetry, SLA health and dashboard summary endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.config import settings
from app.core import redis_client
from app.core.database import get_db
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import CircuitStatus, DeviceStatus, WorkOrderStatus
from app.models.telemetry import TelemetrySample
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workorder import WorkOrder
from app.schemas.availability import CircuitAvailabilityOut
from app.schemas.telemetry import (
    CircuitHealth,
    TelemetrySampleIn,
    TelemetrySampleOut,
)
from app.services import alarm_service, dashboard_service, health_snapshot_service, telemetry_service

router = APIRouter()


@router.post("/samples", response_model=TelemetrySampleOut, status_code=201)
def push_sample(
    payload: TelemetrySampleIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    sample = telemetry_service.record_sample(db, **payload.model_dump())
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/circuits/{circuit_id}/samples", response_model=list[TelemetrySampleOut])
def circuit_samples(
    circuit_id: int,
    limit: int = 120,
    hours: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return telemetry_service.list_circuit_samples(
        db, circuit_id, limit=limit, hours=hours
    )


@router.get("/circuits/{circuit_id}/traffic-summary")
def circuit_traffic_summary(
    circuit_id: int,
    limit: int = 120,
    hours: int | None = 24,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Traffic samples plus in-window 95th percentile for chart overlay."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if (start_at and not end_at) or (end_at and not start_at):
        raise HTTPException(status_code=400, detail="start_at and end_at must be provided together")
    if start_at and end_at and start_at >= end_at:
        raise HTTPException(status_code=400, detail="start_at must be before end_at")
    return telemetry_service.traffic_summary_payload(
        db,
        circuit,
        limit=limit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/circuits/{circuit_id}/availability", response_model=CircuitAvailabilityOut)
def circuit_availability(
    circuit_id: int,
    hours: int = 24,
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services import availability_service

    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if (start_at and not end_at) or (end_at and not start_at):
        raise HTTPException(status_code=400, detail="start_at and end_at must be provided together")
    if start_at and end_at and start_at >= end_at:
        raise HTTPException(status_code=400, detail="start_at must be before end_at")
    return availability_service.compute_availability(
        db,
        circuit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/circuits/{circuit_id}/billing")
def circuit_billing(
    circuit_id: int,
    period: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """95th-percentile (月95) bandwidth billing for a circuit."""
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    return telemetry_service.billing_95th(db, circuit, period)


@router.get("/circuits/{circuit_id}/health", response_model=CircuitHealth)
def circuit_health(
    circuit_id: int,
    limit: int = 5000,
    hours: int | None = Query(None),
    start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    circuit = db.get(Circuit, circuit_id)
    if not circuit:
        raise HTTPException(status_code=404, detail="circuit not found")
    if (start_at and not end_at) or (end_at and not start_at):
        raise HTTPException(status_code=400, detail="start_at and end_at must be provided together")
    if start_at and end_at and start_at >= end_at:
        raise HTTPException(status_code=400, detail="start_at must be before end_at")
    windowed = hours is not None or (start_at is not None and end_at is not None)
    if not windowed:
        cache_key = health_snapshot_service.cache_key_health(circuit_id)
        cached = redis_client.cache_get_json(cache_key)
        if cached:
            return CircuitHealth(**cached)
        snap_health = health_snapshot_service.get_snapshot_health(db, circuit)
        if snap_health is not None:
            redis_client.cache_set_json(
                cache_key,
                snap_health.model_dump(),
                settings.redis_health_ttl_seconds,
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
            health_snapshot_service.cache_key_health(circuit_id),
            health.model_dump(),
            settings.redis_health_ttl_seconds,
        )
    return health


@router.post("/collect", response_model=dict)
def collect_telemetry(
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Collect one SNMP telemetry sample for every active circuit."""
    circuits = db.execute(
        select(Circuit).where(Circuit.status == CircuitStatus.ACTIVE)
    ).scalars().all()
    count = 0
    skipped = 0
    for c in circuits:
        sample = telemetry_service.collect_circuit_sample(db, c)
        if sample:
            count += 1
        else:
            skipped += 1
    db.flush()
    for c in circuits:
        health = telemetry_service.compute_health(db, c)
        health_snapshot_service.upsert_from_health(db, c.id, health)
        health_snapshot_service.invalidate_circuit(c)
        alarm_service.evaluate_circuit_health(db, c, health)
        alarm_service.evaluate_circuit_availability(db, c)
    db.commit()
    from app.services import snmp_settings as snmp_cfg

    snmp = snmp_cfg.get_or_create(db)
    return {
        "collected": count,
        "skipped": skipped,
        "generated": count,
        "snmp_enabled": snmp.enabled,
        "message": "SNMP 采集完成" if count else "无 SNMP 采样（请检查 SNMP 配置与设备接口 ifIndex）",
    }


@router.post("/simulate", response_model=dict, deprecated=True)
def simulate(
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Deprecated alias for /telemetry/collect."""
    return collect_telemetry(db, user)


@router.get("/overview")
def overview(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Aggregate traffic trend across all circuits (per-minute buckets)."""
    cache_key = health_snapshot_service.cache_key_overview(hours)
    cached = redis_client.cache_get_json(cache_key)
    if cached:
        return cached
    data = telemetry_service.overview_traffic(db, hours=hours)
    redis_client.cache_set_json(
        cache_key, data, settings.redis_overview_ttl_seconds
    )
    return data


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregate KPIs for the operations overview screen."""
    return dashboard_service.dashboard_kpis(db)


@router.get("/dashboard-overview")
def dashboard_overview(
    hours: int = 24,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Single payload for the operations home dashboard."""
    return dashboard_service.operations_overview(db, hours=hours)
