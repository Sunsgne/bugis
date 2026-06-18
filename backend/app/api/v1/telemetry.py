"""Telemetry, SLA health and dashboard summary endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
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
from app.services import alarm_service, telemetry_service

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
    samples = telemetry_service.list_circuit_samples(
        db,
        circuit_id,
        limit=limit,
        hours=hours if not (start_at and end_at) else None,
        start_at=start_at,
        end_at=end_at,
    )
    p95 = telemetry_service.chart_p95(samples) if samples else {
        "in_95_mbps": 0.0,
        "out_95_mbps": 0.0,
        "billable_95_mbps": 0.0,
    }
    return {
        "circuit_id": circuit_id,
        "samples": samples,
        "p95": p95,
        "bandwidth_mbps": circuit.bandwidth_mbps,
    }


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
    return telemetry_service.compute_health(
        db,
        circuit,
        limit=limit,
        hours=hours,
        start_at=start_at,
        end_at=end_at,
    )


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
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregate traffic trend across all circuits (per-minute buckets)."""
    return telemetry_service.overview_traffic(db)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Aggregate KPIs for the operations overview screen."""
    tenant_count = db.scalar(select(func.count(Tenant.id))) or 0
    device_count = db.scalar(select(func.count(Device.id))) or 0
    online_devices = db.scalar(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
    ) or 0
    circuit_count = db.scalar(select(func.count(Circuit.id))) or 0
    active_circuits = db.scalar(
        select(func.count(Circuit.id)).where(Circuit.status == CircuitStatus.ACTIVE)
    ) or 0
    total_bandwidth = db.scalar(
        select(func.coalesce(func.sum(Circuit.bandwidth_mbps), 0)).where(
            Circuit.status == CircuitStatus.ACTIVE
        )
    ) or 0
    open_work_orders = db.scalar(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.status.notin_(
                [WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]
            )
        )
    ) or 0

    circuits_by_status: dict[str, int] = {}
    for status_row in db.execute(
        select(Circuit.status, func.count(Circuit.id)).group_by(Circuit.status)
    ).all():
        circuits_by_status[status_row[0].value] = status_row[1]

    devices_by_vendor: dict[str, int] = {}
    for row in db.execute(
        select(Device.vendor, func.count(Device.id)).group_by(Device.vendor)
    ).all():
        devices_by_vendor[row[0].value] = row[1]

    return {
        "tenants": tenant_count,
        "devices": device_count,
        "devices_online": online_devices,
        "circuits": circuit_count,
        "circuits_active": active_circuits,
        "total_active_bandwidth_mbps": int(total_bandwidth),
        "work_orders": open_work_orders,
        "circuits_by_status": circuits_by_status,
        "devices_by_vendor": devices_by_vendor,
    }
