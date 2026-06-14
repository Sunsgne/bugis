"""Shared enumerations used across models, schemas and services."""
from __future__ import annotations

import enum


class Vendor(str, enum.Enum):
    """Supported network equipment vendors."""

    H3C = "h3c"
    HUAWEI = "huawei"
    JUNIPER = "juniper"
    ARISTA = "arista"
    CISCO = "cisco"
    FRR = "frr"  # FRRouting (开源 / 白盒 SONiC 演进)


class OverlayTech(str, enum.Enum):
    """Overlay / transport technology used by a device or circuit."""

    VXLAN_EVPN = "vxlan_evpn"  # 华三/华为 BGP EVPN VXLAN
    SRMPLS_EVPN = "srmpls_evpn"  # Juniper/Arista/Cisco SR-MPLS EVPN


class DeviceRole(str, enum.Enum):
    """Functional role of a device in the fabric."""

    SPINE = "spine"
    LEAF = "leaf"
    BORDER_LEAF = "border_leaf"
    VTEP = "vtep"
    PE = "pe"  # provider edge (MPLS)
    P = "p"  # provider core (MPLS)
    RR = "rr"  # route reflector
    DCI_GW = "dci_gw"  # DCI gateway
    CPE = "cpe"  # customer premise / access


class DeviceStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class TenantType(str, enum.Enum):
    """Tenant business / access type."""

    ENTERPRISE = "enterprise"  # 企业专线
    HYBRID_CLOUD = "hybrid_cloud"  # 混合云接入
    PUBLIC_CLOUD = "public_cloud"  # 公有云接入
    INTERNAL = "internal"  # 内部业务


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ServiceType(str, enum.Enum):
    """Type of L2/L3 service the circuit delivers."""

    L2VPN_EVPN = "l2vpn_evpn"  # EVPN E-LINE / E-LAN
    L3VPN_EVPN = "l3vpn_evpn"  # EVPN IRB / L3VPN
    EVPN_VPWS = "evpn_vpws"  # point-to-point
    DCI = "dci"  # data center interconnect


class CircuitStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    DECOMMISSIONED = "decommissioned"
    FAILED = "failed"


class WorkOrderType(str, enum.Enum):
    PROVISION = "provision"  # 开通
    MODIFY = "modify"  # 变更（带宽/参数）
    DECOMMISSION = "decommission"  # 拆除
    MIGRATE = "migrate"  # 迁移


class WorkOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ConfigJobStatus(str, enum.Enum):
    PENDING = "pending"
    RENDERED = "rendered"
    DRY_RUN = "dry_run"
    PUSHING = "pushing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AlarmSeverity(str, enum.Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"
    INFO = "info"


class AlarmStatus(str, enum.Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


class LinkType(str, enum.Enum):
    """Physical / logical link between two devices."""

    INTRA_DC = "intra_dc"  # 同 DC 内 (spine-leaf)
    DCI = "dci"  # 跨 DC 互联
    ACCESS = "access"  # 接入侧
    UPLINK = "uplink"  # 上联
