"""Bugis - DCI / EVPN 专线开通与运营平台 - application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Gauge,
    generate_latest,
)
from sqlalchemy import func, select
from starlette.responses import Response

from app import __version__
from app.api.v1 import api_router
from app.bootstrap import ensure_bugis_controller, ensure_superuser
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.models.alarm import Alarm
from app.models.circuit import Circuit
from app.models.device import Device
from app.models.enums import AlarmStatus, CircuitStatus
from app.models.tenant import Tenant

# --- Prometheus metrics ----------------------------------------------------
CIRCUITS_TOTAL = Gauge("bugis_circuits_total", "Total number of circuits")
CIRCUITS_ACTIVE = Gauge("bugis_circuits_active", "Number of active circuits")
DEVICES_TOTAL = Gauge("bugis_devices_total", "Total number of devices")
TENANTS_TOTAL = Gauge("bugis_tenants_total", "Total number of tenants")
ACTIVE_BANDWIDTH = Gauge(
    "bugis_active_bandwidth_mbps", "Sum of active circuit bandwidth (Mbps)"
)
ACTIVE_ALARMS = Gauge("bugis_active_alarms", "Number of active (uncleared) alarms")
CIRCUITS_BY_STATUS = Gauge(
    "bugis_circuits_by_status", "Circuits grouped by status", ["status"]
)
DEVICES_BY_VENDOR = Gauge(
    "bugis_devices_by_vendor", "Devices grouped by vendor", ["vendor"]
)
ALARMS_BY_SEVERITY = Gauge(
    "bugis_alarms_by_severity", "Active alarms grouped by severity", ["severity"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_superuser(db)
        ensure_bugis_controller(db)
    finally:
        db.close()
    from app import scheduler

    scheduler.start()
    yield
    await scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "开源 DCI / EVPN 专线开通与运营平台 — multi-vendor (H3C/Huawei VXLAN-EVPN, "
        "Juniper/Arista/Cisco SR-MPLS-EVPN) provisioning & operations."
    ),
    lifespan=lifespan,
)

from app.middleware import AuditMiddleware  # noqa: E402

app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": __version__, "dry_run": settings.dry_run}


@app.get("/metrics", include_in_schema=False)
def metrics():
    if not settings.enable_metrics:
        return Response(status_code=404)
    db = SessionLocal()
    try:
        CIRCUITS_TOTAL.set(db.scalar(select(func.count(Circuit.id))) or 0)
        CIRCUITS_ACTIVE.set(
            db.scalar(
                select(func.count(Circuit.id)).where(
                    Circuit.status == CircuitStatus.ACTIVE
                )
            ) or 0
        )
        DEVICES_TOTAL.set(db.scalar(select(func.count(Device.id))) or 0)
        TENANTS_TOTAL.set(db.scalar(select(func.count(Tenant.id))) or 0)
        ACTIVE_BANDWIDTH.set(
            db.scalar(
                select(func.coalesce(func.sum(Circuit.bandwidth_mbps), 0)).where(
                    Circuit.status == CircuitStatus.ACTIVE
                )
            ) or 0
        )
        ACTIVE_ALARMS.set(
            db.scalar(
                select(func.count(Alarm.id)).where(Alarm.status != AlarmStatus.CLEARED)
            ) or 0
        )
        from app.models.enums import AlarmSeverity, Vendor

        status_counts = {
            row[0].value: row[1]
            for row in db.execute(
                select(Circuit.status, func.count(Circuit.id)).group_by(Circuit.status)
            ).all()
        }
        for st in CircuitStatus:
            CIRCUITS_BY_STATUS.labels(status=st.value).set(
                status_counts.get(st.value, 0)
            )

        vendor_counts = {
            row[0].value: row[1]
            for row in db.execute(
                select(Device.vendor, func.count(Device.id)).group_by(Device.vendor)
            ).all()
        }
        for v in Vendor:
            DEVICES_BY_VENDOR.labels(vendor=v.value).set(vendor_counts.get(v.value, 0))

        sev_counts = {
            row[0].value: row[1]
            for row in db.execute(
                select(Alarm.severity, func.count(Alarm.id))
                .where(Alarm.status != AlarmStatus.CLEARED)
                .group_by(Alarm.severity)
            ).all()
        }
        for s in AlarmSeverity:
            ALARMS_BY_SEVERITY.labels(severity=s.value).set(sev_counts.get(s.value, 0))
    finally:
        db.close()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
