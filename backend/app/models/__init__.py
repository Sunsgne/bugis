"""ORM models package. Import all models so SQLAlchemy metadata is complete."""
from app.models.user import User  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.site import Site  # noqa: F401
from app.models.device import Device, DeviceInterface  # noqa: F401
from app.models.circuit import Circuit, CircuitEndpoint, CircuitPathHop  # noqa: F401
from app.models.workorder import WorkOrder, WorkOrderEvent  # noqa: F401
from app.models.config_job import ConfigJob  # noqa: F401
from app.models.telemetry import TelemetrySample  # noqa: F401
from app.models.alarm import Alarm  # noqa: F401
from app.models.link import Link  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.offering import ServiceOffering  # noqa: F401
from app.models.controller import Controller  # noqa: F401
from app.models.notification import NotificationChannel  # noqa: F401
from app.models.controlplane import (  # noqa: F401
    BgpEvpnSession,
    ControllerClusterNode,
    DataPlaneBinding,
    EvpnRoute,
    VtepPeer,
)
from app.models.platform_settings import PlatformSettings  # noqa: F401
from app.models.snmp_settings import SnmpSettings  # noqa: F401
from app.models.config_snapshot import DeviceConfigSnapshot  # noqa: F401

__all__ = [
    "User",
    "Tenant",
    "Site",
    "Device",
    "DeviceInterface",
    "Circuit",
    "CircuitEndpoint",
    "CircuitPathHop",
    "WorkOrder",
    "WorkOrderEvent",
    "ConfigJob",
    "TelemetrySample",
    "Alarm",
    "Link",
    "AuditLog",
    "ServiceOffering",
    "Controller",
    "NotificationChannel",
    "VtepPeer",
    "EvpnRoute",
    "BgpEvpnSession",
    "ControllerClusterNode",
    "DataPlaneBinding",
    "DeviceConfigSnapshot",
    "SnmpSettings",
    "PlatformSettings",
]
