"""Operations dashboard — single payload for the home screen."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import scheduler
from app.core.config import settings
from app.core import redis_client
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import AlarmStatus, CircuitStatus, DeviceStatus, WorkOrderStatus
from app.models.link import Link
from app.models.tenant import Tenant
from app.models.workorder import WorkOrder
from app.services import capacity_service, health_snapshot_service, link_monitor, telemetry_service
from app.controller import controller as bugis_controller


def dashboard_kpis(db: Session) -> dict:
    """Aggregate KPI counters (same shape as GET /telemetry/dashboard)."""
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
        "tenants": int(db.scalar(select(func.count(Tenant.id))) or 0),
        "devices": int(db.scalar(select(func.count(Device.id))) or 0),
        "devices_online": int(
            db.scalar(
                select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
            )
            or 0
        ),
        "circuits": int(db.scalar(select(func.count(Circuit.id))) or 0),
        "circuits_active": int(
            db.scalar(
                select(func.count(Circuit.id)).where(Circuit.status == CircuitStatus.ACTIVE)
            )
            or 0
        ),
        "total_active_bandwidth_mbps": int(
            db.scalar(
                select(func.coalesce(func.sum(Circuit.bandwidth_mbps), 0)).where(
                    Circuit.status == CircuitStatus.ACTIVE
                )
            )
            or 0
        ),
        "work_orders": int(
            db.scalar(
                select(func.count(WorkOrder.id)).where(
                    WorkOrder.status.notin_(
                        [WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]
                    )
                )
            )
            or 0
        ),
        "circuits_by_status": circuits_by_status,
        "devices_by_vendor": devices_by_vendor,
    }


def _alarm_summary(db: Session) -> dict:
    by_sev: dict[str, int] = {}
    for row in db.execute(
        select(Alarm.severity, func.count(Alarm.id))
        .where(Alarm.status != AlarmStatus.CLEARED)
        .group_by(Alarm.severity)
    ).all():
        by_sev[row[0].value] = row[1]
    active = int(
        db.scalar(
            select(func.count(Alarm.id)).where(Alarm.status == AlarmStatus.ACTIVE)
        )
        or 0
    )
    return {"active": active, "by_severity": by_sev}


def _link_summaries(db: Session, links: list[Link], health_by_id: dict) -> list[dict]:
    rows: list[dict] = []
    for link in links:
        health = health_by_id.get(link.id)
        rows.append(
            {
                "link_id": link.id,
                "name": link.name,
                "type": link.type.value,
                "capacity_mbps": link.capacity_mbps,
                "utilization_pct": health.peak_utilization_pct if health else 0.0,
            }
        )
    return rows


def _recent_work_orders(db: Session, *, limit: int = 6) -> list[dict]:
    rows = db.execute(
        select(WorkOrder).order_by(WorkOrder.id.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": wo.id,
            "code": wo.code,
            "type": wo.type.value,
            "status": wo.status.value,
            "created_at": wo.created_at.isoformat() if wo.created_at else None,
        }
        for wo in rows
    ]


def _traffic_overview(db: Session, *, hours: int = 1) -> list:
    """Recent per-minute circuit traffic for the home dashboard chart."""
    cache_key = health_snapshot_service.cache_key_overview(hours)
    cached = redis_client.cache_get_json(cache_key)
    if cached is not None:
        return cached
    data = telemetry_service.overview_traffic(db, hours=hours)
    redis_client.cache_set_json(
        cache_key, data, settings.redis_overview_ttl_seconds
    )
    return data


def operations_overview(db: Session, *, hours: int = 24) -> dict:
    """Home dashboard payload in one DB session."""
    cache_key = f"{settings.redis_key_prefix}:dashboard:overview:{hours}"
    cached = redis_client.cache_get_json(cache_key)
    if cached is not None:
        return cached

    links = db.execute(select(Link)).scalars().all()
    health_by_id = link_monitor.batch_compute_link_health(db, links)

    payload = {
        "dashboard": dashboard_kpis(db),
        "traffic": _traffic_overview(db),
        "alarms": _alarm_summary(db),
        "sdn": bugis_controller.status(db),
        "sites": capacity_service.site_capacity(db),
        "links": _link_summaries(db, links, health_by_id),
        "work_orders": _recent_work_orders(db),
        "scheduler": scheduler.status(),
    }
    redis_client.cache_set_json(cache_key, payload, 30)
    return payload
