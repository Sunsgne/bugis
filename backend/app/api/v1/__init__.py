"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import (
    alarms,
    audit,
    auth,
    bulk,
    capacity,
    circuits,
    config_mgmt,
    controllers,
    controlplane,
    devices,
    drivers,
    integrations,
    notifications,
    offerings,
    sites,
    stream,
    system,
    telemetry,
    tenants,
    workorders,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(
    controllers.router, prefix="/controllers", tags=["controllers"]
)
api_router.include_router(
    controlplane.router, prefix="/controller", tags=["sdn-controller"]
)
api_router.include_router(
    offerings.router, prefix="/offerings", tags=["offerings"]
)
api_router.include_router(circuits.router, prefix="/circuits", tags=["circuits"])
api_router.include_router(
    workorders.router, prefix="/work-orders", tags=["work-orders"]
)
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(capacity.router, prefix="/capacity", tags=["capacity"])
api_router.include_router(
    integrations.router, prefix="/integrations", tags=["integrations"]
)
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(
    config_mgmt.router, prefix="/config", tags=["config-management"]
)
api_router.include_router(bulk.router, prefix="/bulk", tags=["bulk"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(drivers.router, prefix="/drivers", tags=["drivers"])
