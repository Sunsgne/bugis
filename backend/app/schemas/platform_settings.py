"""Platform settings schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class PlatformSettingsBase(BaseModel):
    dry_run: bool = True
    netconf_timeout: int = Field(default=30, ge=5, le=300)

    baseline_ntp_server: str = "10.0.0.1"
    baseline_syslog_server: str = "10.0.0.2"

    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = Field(default=30, ge=10, le=3600)

    threshold_packet_loss_pct: float = Field(default=0.5, ge=0, le=100)
    threshold_latency_ms: float = Field(default=50.0, ge=0, le=10000)
    threshold_utilization_pct: float = Field(default=90.0, ge=0, le=100)
    threshold_health_score: float = Field(default=70.0, ge=0, le=100)
    threshold_link_utilization_pct: float = Field(default=85.0, ge=0, le=100)

    controller_bgp_asn: int = Field(default=65000, ge=1, le=4294967295)
    controller_node_id: str = "bugis-1"

    webhook_token: str = "bugis-webhook-token"

    smtp_host: str = ""
    smtp_port: int = Field(default=25, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str | None = None
    smtp_from: str = "bugis@localhost"

    enable_metrics: bool = True
    access_token_expire_minutes: int = Field(default=1440, ge=5, le=60 * 24 * 30)

    notes: str | None = None


class PlatformSettingsUpdate(BaseModel):
    dry_run: bool | None = None
    netconf_timeout: int | None = Field(default=None, ge=5, le=300)

    baseline_ntp_server: str | None = None
    baseline_syslog_server: str | None = None

    scheduler_enabled: bool | None = None
    scheduler_interval_seconds: int | None = Field(default=None, ge=10, le=3600)

    threshold_packet_loss_pct: float | None = Field(default=None, ge=0, le=100)
    threshold_latency_ms: float | None = Field(default=None, ge=0, le=10000)
    threshold_utilization_pct: float | None = Field(default=None, ge=0, le=100)
    threshold_health_score: float | None = Field(default=None, ge=0, le=100)
    threshold_link_utilization_pct: float | None = Field(default=None, ge=0, le=100)

    controller_bgp_asn: int | None = Field(default=None, ge=1, le=4294967295)
    controller_node_id: str | None = None

    webhook_token: str | None = None

    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    enable_metrics: bool | None = None
    access_token_expire_minutes: int | None = Field(default=None, ge=5, le=60 * 24 * 30)

    notes: str | None = None


class PlatformSettingsOut(PlatformSettingsBase, TimestampedSchema):
    id: int
    smtp_password_set: bool = False


class PlatformReadonlyInfo(BaseModel):
    version: str
    app_env: str
    app_name: str
    database_url: str
    secret_key_set: bool


class AllSettingsOut(BaseModel):
    platform: PlatformSettingsOut
    readonly: PlatformReadonlyInfo
