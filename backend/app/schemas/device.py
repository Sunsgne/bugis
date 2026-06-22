"""Device & interface schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.ip_validation import validate_ip_address
from app.models.enums import DeviceRole, DeviceStatus, ManagementTransport, OverlayTech, Vendor
from app.schemas.common import TimestampedSchema


class SvidUsageOut(BaseModel):
    s_vid: int | None = None
    c_vid: int | None = None
    access_mode: str = "dot1q"
    circuit_code: str | None = None
    source: str = "platform"
    note: str | None = None
    description: str | None = None
    rate_limit_mbps: int | None = None
    vni: int | None = None
    vsi_name: str | None = None
    tenant_name: str | None = None
    tenant_code: str | None = None
    circuit_name: str | None = None
    bandwidth_mbps: int | None = None


class DeviceInterfaceBase(BaseModel):
    name: str
    description: str | None = None
    speed_mbps: int | None = None
    admin_up: bool = True
    allocated: bool = False
    used_s_vids: list[SvidUsageOut] | None = None
    ifindex: int | None = None
    oper_status: str | None = None
    discovered_via: str | None = None


class DeviceInterfaceCreate(DeviceInterfaceBase):
    pass


class DeviceInterfaceOut(DeviceInterfaceBase, TimestampedSchema):
    id: int
    device_id: int


class InterfaceDescriptionItem(BaseModel):
    name: str
    description: str | None = None


class InterfaceDescriptionBulkIn(BaseModel):
    items: list[InterfaceDescriptionItem]
    push: bool = True


class InterfaceDescriptionResult(BaseModel):
    name: str
    description: str | None = None
    updated: bool
    note: str | None = None


class InterfaceDescriptionBulkOut(BaseModel):
    device: str
    updated: int
    pushed: bool
    dry_run: bool
    output: str | None = None
    rendered: str | None = None
    results: list[InterfaceDescriptionResult] = []


class DeviceInterfaceDescriptionBatchItem(BaseModel):
    device_id: int
    items: list[InterfaceDescriptionItem]


class InterfaceDescriptionMultiBulkIn(BaseModel):
    devices: list[DeviceInterfaceDescriptionBatchItem]
    push: bool = True


class InterfaceDescriptionMultiBulkOut(BaseModel):
    results: list[InterfaceDescriptionBulkOut]
    total_updated: int
    all_pushed: bool
    dry_run: bool


class DeviceLearnBatchIn(BaseModel):
    device_ids: list[int] = Field(..., min_length=1)
    max_workers: int | None = Field(None, ge=1, le=16)


class DeviceLearnBatchOut(BaseModel):
    total: int
    success: int
    failed: int
    max_workers: int
    results: list[dict]


class DevicePortBindingOut(BaseModel):
    interface_name: str
    binding_type: str  # platform | device
    tenant_id: int | None = None
    tenant_name: str | None = None
    tenant_code: str | None = None
    business_name: str | None = None
    circuit_id: int | None = None
    circuit_code: str | None = None
    circuit_name: str | None = None
    circuit_status: str | None = None
    endpoint_label: str | None = None
    access_mode: str = "dot1q"
    s_vid: int | None = None
    c_vid: int | None = None
    vni: int | None = None
    vsi_name: str | None = None
    description: str | None = None
    rate_limit_mbps: int | None = None
    bandwidth_mbps: int | None = None
    source: str = "platform"
    note: str | None = None


class DevicePortBindingsOut(BaseModel):
    device_id: int
    device: str
    total_bindings: int
    platform_bindings: int
    device_only_bindings: int
    bound_interfaces: int
    unbound_interfaces: list[str] = []
    items: list[DevicePortBindingOut] = []


class DeviceBase(BaseModel):
    name: str
    hostname: str | None = None
    vendor: Vendor
    model: str | None = None
    os_version: str | None = None
    role: DeviceRole = DeviceRole.LEAF
    overlay_tech: OverlayTech = OverlayTech.VXLAN_EVPN
    status: DeviceStatus = DeviceStatus.UNKNOWN
    mgmt_ip: str
    mgmt_ip_backup: str | None = None
    mgmt_ip_primary_label: str | None = "管理网"
    mgmt_ip_backup_label: str | None = "公网"
    mgmt_ip_active: str | None = None
    mgmt_ip_active_role: str | None = None
    last_reachability_at: datetime | None = None
    last_reachability_latency_ms: float | None = None
    last_reachability_method: str | None = None
    management_transport: ManagementTransport = ManagementTransport.AUTO
    netconf_port: int = 830
    ssh_port: int = 22
    username: str | None = None
    password: str | None = None
    enable_password: str | None = None
    netmiko_device_type: str | None = None
    snmp_enabled: bool = True
    snmp_port: int = Field(default=161, ge=1, le=65535)
    snmp_community: str | None = None
    snmp_version: str = "2c"
    snmp_v3_username: str | None = None
    snmp_v3_auth_password: str | None = None
    snmp_v3_priv_password: str | None = None
    snmp_v3_security_level: str | None = None
    snmp_v3_auth_protocol: str | None = None
    snmp_v3_priv_protocol: str | None = None
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    sr_node_sid: int | None = None
    is_route_reflector: bool = False
    site_id: int | None = None


class DeviceCreate(DeviceBase):
    @field_validator("mgmt_ip")
    @classmethod
    def _validate_mgmt_ip(cls, v: str) -> str:
        return validate_ip_address(v, field="mgmt_ip", required=True)  # type: ignore[return-value]

    @field_validator("mgmt_ip_backup", "loopback_ip")
    @classmethod
    def _validate_optional_ip(cls, v: str | None) -> str | None:
        return validate_ip_address(v, field="ip")


class DeviceUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    model: str | None = None
    os_version: str | None = None
    role: DeviceRole | None = None
    overlay_tech: OverlayTech | None = None
    status: DeviceStatus | None = None
    mgmt_ip: str | None = None
    mgmt_ip_backup: str | None = None
    mgmt_ip_primary_label: str | None = None
    mgmt_ip_backup_label: str | None = None
    management_transport: ManagementTransport | None = None
    netconf_port: int | None = None
    ssh_port: int | None = None
    username: str | None = None
    password: str | None = None
    enable_password: str | None = None
    netmiko_device_type: str | None = None
    snmp_enabled: bool | None = None
    snmp_port: int | None = Field(default=None, ge=1, le=65535)
    snmp_community: str | None = None
    snmp_version: str | None = None
    snmp_v3_username: str | None = None
    snmp_v3_auth_password: str | None = None
    snmp_v3_priv_password: str | None = None
    snmp_v3_security_level: str | None = None
    snmp_v3_auth_protocol: str | None = None
    snmp_v3_priv_protocol: str | None = None
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    sr_node_sid: int | None = None
    is_route_reflector: bool | None = None
    site_id: int | None = None

    @field_validator("mgmt_ip", "mgmt_ip_backup", "loopback_ip")
    @classmethod
    def _validate_optional_ip(cls, v: str | None) -> str | None:
        return validate_ip_address(v, field="ip")


class DeviceListOut(DeviceBase, TimestampedSchema):
    """Device summary for list views (no interface payload)."""

    id: int
    password: str | None = Field(default=None, exclude=True)
    password_set: bool = False
    enable_password: str | None = Field(default=None, exclude=True)
    enable_password_set: bool = False
    snmp_community: str | None = Field(default=None, exclude=True)
    snmp_community_set: bool = False
    snmp_v3_auth_password: str | None = Field(default=None, exclude=True)
    snmp_v3_auth_password_set: bool = False
    snmp_v3_priv_password: str | None = Field(default=None, exclude=True)
    snmp_v3_priv_password_set: bool = False

    @model_validator(mode="before")
    @classmethod
    def _flag_secrets(cls, data):
        from app.models.device import Device

        if isinstance(data, Device):
            payload = {c.key: getattr(data, c.key) for c in Device.__table__.columns}
            payload["password_set"] = bool(data.password)
            payload["enable_password_set"] = bool(data.enable_password)
            payload["snmp_community_set"] = bool(data.snmp_community)
            payload["snmp_v3_auth_password_set"] = bool(data.snmp_v3_auth_password)
            payload["snmp_v3_priv_password_set"] = bool(data.snmp_v3_priv_password)
            return payload
        if isinstance(data, dict):
            data = dict(data)
            data["password_set"] = bool(data.get("password"))
            data["enable_password_set"] = bool(data.get("enable_password"))
            data["snmp_community_set"] = bool(data.get("snmp_community"))
            data["snmp_v3_auth_password_set"] = bool(data.get("snmp_v3_auth_password"))
            data["snmp_v3_priv_password_set"] = bool(data.get("snmp_v3_priv_password"))
        return data


class DeviceOut(DeviceBase, TimestampedSchema):
    id: int
    # Never expose stored credentials in API responses.
    password: str | None = Field(default=None, exclude=True)
    interfaces: list[DeviceInterfaceOut] = []
