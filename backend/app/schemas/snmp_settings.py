"""SNMP settings schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class SnmpSettingsBase(BaseModel):
    enabled: bool = True
    version: str = Field(default="2c", pattern="^(2c|3)$")

    community: str = "bugis-ro"
    write_community: str | None = None

    port: int = Field(default=161, ge=1, le=65535)
    timeout_sec: float = Field(default=2.0, ge=0.5, le=60)
    retries: int = Field(default=1, ge=0, le=10)
    max_repetitions: int = Field(default=25, ge=1, le=100)

    prefer_device_community: bool = True

    walk_if_descr: bool = True
    walk_if_alias: bool = True
    walk_if_high_speed: bool = True
    walk_if_oper_status: bool = True

    sync_link_capacity: bool = True
    auto_discover_on_check: bool = False

    exclude_name_patterns: list[str] | None = None
    include_name_patterns: list[str] | None = None

    v3_username: str | None = None
    v3_security_level: str = "authPriv"
    v3_auth_protocol: str | None = None
    v3_auth_password: str | None = None
    v3_priv_protocol: str | None = None
    v3_priv_password: str | None = None
    v3_context_name: str | None = None

    baseline_community: str = "bugis-ro"
    notes: str | None = None


class SnmpSettingsUpdate(BaseModel):
    enabled: bool | None = None
    version: str | None = Field(default=None, pattern="^(2c|3)$")

    community: str | None = None
    write_community: str | None = None

    port: int | None = Field(default=None, ge=1, le=65535)
    timeout_sec: float | None = Field(default=None, ge=0.5, le=60)
    retries: int | None = Field(default=None, ge=0, le=10)
    max_repetitions: int | None = Field(default=None, ge=1, le=100)

    prefer_device_community: bool | None = None

    walk_if_descr: bool | None = None
    walk_if_alias: bool | None = None
    walk_if_high_speed: bool | None = None
    walk_if_oper_status: bool | None = None

    sync_link_capacity: bool | None = None
    auto_discover_on_check: bool | None = None

    exclude_name_patterns: list[str] | None = None
    include_name_patterns: list[str] | None = None

    v3_username: str | None = None
    v3_security_level: str | None = None
    v3_auth_protocol: str | None = None
    v3_auth_password: str | None = None
    v3_priv_protocol: str | None = None
    v3_priv_password: str | None = None
    v3_context_name: str | None = None

    baseline_community: str | None = None
    notes: str | None = None


class SnmpSettingsOut(SnmpSettingsBase, TimestampedSchema):
    id: int
    v3_auth_password_set: bool = False
    v3_priv_password_set: bool = False


class SnmpTestRequest(BaseModel):
    device_id: int | None = None
    mgmt_ip: str | None = None
    community: str | None = None


class SnmpTestResponse(BaseModel):
    ok: bool
    target: str
    version: str
    interfaces_found: int = 0
    sample_interfaces: list[str] = []
    latency_ms: float | None = None
    detail: str | None = None
