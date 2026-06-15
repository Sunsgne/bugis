"""Device & interface schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DeviceRole, DeviceStatus, OverlayTech, Vendor
from app.schemas.common import TimestampedSchema


class SvidUsageOut(BaseModel):
    s_vid: int | None = None
    c_vid: int | None = None
    access_mode: str = "dot1q"
    circuit_code: str | None = None
    source: str = "platform"
    note: str | None = None


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
    netconf_port: int = 830
    ssh_port: int = 22
    username: str | None = None
    password: str | None = None
    snmp_enabled: bool = True
    snmp_port: int = Field(default=161, ge=1, le=65535)
    snmp_community: str | None = None
    snmp_version: str = "2c"
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    sr_node_sid: int | None = None
    is_route_reflector: bool = False
    site_id: int | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    model: str | None = None
    os_version: str | None = None
    role: DeviceRole | None = None
    overlay_tech: OverlayTech | None = None
    status: DeviceStatus | None = None
    mgmt_ip: str | None = None
    netconf_port: int | None = None
    ssh_port: int | None = None
    username: str | None = None
    password: str | None = None
    snmp_enabled: bool | None = None
    snmp_port: int | None = Field(default=None, ge=1, le=65535)
    snmp_community: str | None = None
    snmp_version: str | None = None
    loopback_ip: str | None = None
    bgp_asn: int | None = None
    sr_node_sid: int | None = None
    is_route_reflector: bool | None = None
    site_id: int | None = None


class DeviceListOut(DeviceBase, TimestampedSchema):
    """Device summary for list views (no interface payload)."""

    id: int
    password: str | None = Field(default=None, exclude=True)
    password_set: bool = False
    snmp_community: str | None = Field(default=None, exclude=True)
    snmp_community_set: bool = False

    @model_validator(mode="before")
    @classmethod
    def _flag_secrets(cls, data):
        from app.models.device import Device

        if isinstance(data, Device):
            payload = {c.key: getattr(data, c.key) for c in Device.__table__.columns}
            payload["password_set"] = bool(data.password)
            payload["snmp_community_set"] = bool(data.snmp_community)
            return payload
        if isinstance(data, dict):
            data = dict(data)
            data["password_set"] = bool(data.get("password"))
            data["snmp_community_set"] = bool(data.get("snmp_community"))
        return data


class DeviceOut(DeviceBase, TimestampedSchema):
    id: int
    # Never expose stored credentials in API responses.
    password: str | None = Field(default=None, exclude=True)
    interfaces: list[DeviceInterfaceOut] = []
