"""API v1 router aggregation."""
from fastapi import APIRouter, Depends

from app.api.v1 import (
    alarms,
    alarm_templates,
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
    platform_settings,
    portal,
    sites,
    snmp_settings,
    stream,
    system,
    telemetry,
    tenants,
    workorders,
)
from app.api.deps import require_platform_user

api_router = APIRouter()
_platform = [Depends(require_platform_user)]

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"], dependencies=_platform)
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"], dependencies=_platform)
api_router.include_router(devices.router, prefix="/devices", tags=["devices"], dependencies=_platform)
api_router.include_router(
    controllers.router, prefix="/controllers", tags=["controllers"], dependencies=_platform
)
api_router.include_router(
    controlplane.router, prefix="/controller", tags=["sdn-controller"], dependencies=_platform
)
api_router.include_router(circuits.router, prefix="/circuits", tags=["circuits"], dependencies=_platform)
api_router.include_router(
    workorders.router, prefix="/work-orders", tags=["work-orders"], dependencies=_platform
)
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"], dependencies=_platform)
api_router.include_router(alarms.router, prefix="/alarms", tags=["alarms"], dependencies=_platform)
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"], dependencies=_platform
)
api_router.include_router(capacity.router, prefix="/capacity", tags=["capacity"], dependencies=_platform)
api_router.include_router(
    integrations.router, prefix="/integrations", tags=["integrations"]
)
api_router.include_router(audit.router, prefix="/audit", tags=["audit"], dependencies=_platform)
api_router.include_router(
    config_mgmt.router, prefix="/config", tags=["config-management"], dependencies=_platform
)
api_router.include_router(bulk.router, prefix="/bulk", tags=["bulk"], dependencies=_platform)
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(
    platform_settings.router, prefix="/system/settings", tags=["platform-settings"], dependencies=_platform
)
api_router.include_router(
    alarm_templates.router,
    prefix="/system/settings/alarm-templates",
    tags=["alarm-templates"],
    dependencies=_platform,
)
api_router.include_router(
    snmp_settings.router, prefix="/system/snmp", tags=["snmp-settings"], dependencies=_platform
)
api_router.include_router(drivers.router, prefix="/drivers", tags=["drivers"], dependencies=_platform)
