"""Platform settings & branding schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class BrandingOut(BaseModel):
    product_name: str
    header_title: str
    tagline: str
    login_title: str
    login_subtitle: str
    hero_title: str
    hero_subtitle: str
    logo_url: str | None = None
    logo_mark_url: str | None = None
    accent_color: str = "#52c41a"
    login_background: str | None = None


class PlatformSettingsBase(BaseModel):
    dry_run: bool = False
    netconf_timeout: int = Field(default=30, ge=5, le=300)
    ssh_timeout: int = Field(default=30, ge=5, le=300)
    default_netconf_port: int = Field(default=830, ge=1, le=65535)
    default_ssh_port: int = Field(default=22, ge=1, le=65535)
    default_username: str = "admin"

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
    smtp_provider: str = ""
    smtp_security: str = "starttls"

    enable_metrics: bool = True
    auto_learn_on_import: bool = True
    auto_learn_enabled: bool = True
    auto_learn_interval_seconds: int = Field(default=60, ge=30, le=3600)
    snmp_discover_enabled: bool = True
    snmp_discover_interval_seconds: int = Field(default=21600, ge=300, le=86400)
    access_token_expire_minutes: int = Field(default=1440, ge=5, le=60 * 24 * 30)

    login_rate_limit_per_ip: int = Field(default=30, ge=5, le=500)
    login_rate_limit_window_minutes: int = Field(default=15, ge=1, le=120)
    login_lockout_after_failures: int = Field(default=5, ge=1, le=50)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    captcha_after_failures: int = Field(default=3, ge=0, le=50)
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""
    turnstile_secret_key: str | None = None
    mfa_required_platform: bool = False
    mfa_required_portal: bool = False
    mfa_allow_totp: bool = True
    mfa_allow_email: bool = True
    expose_openapi: bool = True
    protect_live_config: bool = True
    snapshot_before_change: bool = True
    async_provisioning: bool = False
    provision_max_concurrency: int = Field(default=4, ge=1, le=64)

    notes: str | None = None


class PlatformSettingsUpdate(BaseModel):
    dry_run: bool | None = None
    netconf_timeout: int | None = Field(default=None, ge=5, le=300)
    ssh_timeout: int | None = Field(default=None, ge=5, le=300)
    default_netconf_port: int | None = Field(default=None, ge=1, le=65535)
    default_ssh_port: int | None = Field(default=None, ge=1, le=65535)
    default_username: str | None = None

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
    smtp_provider: str | None = None
    smtp_security: str | None = None

    enable_metrics: bool | None = None
    auto_learn_on_import: bool | None = None
    auto_learn_enabled: bool | None = None
    auto_learn_interval_seconds: int | None = Field(default=None, ge=30, le=3600)
    snmp_discover_enabled: bool | None = None
    snmp_discover_interval_seconds: int | None = Field(default=None, ge=300, le=86400)
    access_token_expire_minutes: int | None = Field(default=None, ge=5, le=60 * 24 * 30)

    login_rate_limit_per_ip: int | None = Field(default=None, ge=5, le=500)
    login_rate_limit_window_minutes: int | None = Field(default=None, ge=1, le=120)
    login_lockout_after_failures: int | None = Field(default=None, ge=1, le=50)
    login_lockout_minutes: int | None = Field(default=None, ge=1, le=1440)
    captcha_after_failures: int | None = Field(default=None, ge=0, le=50)
    turnstile_enabled: bool | None = None
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    mfa_required_platform: bool | None = None
    mfa_required_portal: bool | None = None
    mfa_allow_totp: bool | None = None
    mfa_allow_email: bool | None = None
    expose_openapi: bool | None = None
    protect_live_config: bool | None = None
    snapshot_before_change: bool | None = None
    async_provisioning: bool | None = None
    provision_max_concurrency: int | None = Field(default=None, ge=1, le=64)

    notes: str | None = None


class BrandingUpdate(BaseModel):
    product_name: str | None = Field(default=None, max_length=128)
    header_title: str | None = Field(default=None, max_length=255)
    tagline: str | None = Field(default=None, max_length=255)
    login_title: str | None = Field(default=None, max_length=128)
    login_subtitle: str | None = Field(default=None, max_length=255)
    hero_title: str | None = Field(default=None, max_length=255)
    hero_subtitle: str | None = Field(default=None, max_length=512)
    logo_url: str | None = None
    logo_mark_url: str | None = None
    accent_color: str | None = Field(default=None, max_length=16)
    login_background: str | None = None


class PlatformAnyUpdate(PlatformSettingsUpdate, BrandingUpdate):
    """Operational and/or branding fields for PATCH /platform."""


class PlatformSettingsOut(PlatformSettingsBase, BrandingOut, TimestampedSchema):
    id: int
    smtp_password_set: bool = False
    turnstile_secret_key_set: bool = False


class PlatformReadonlyInfo(BaseModel):
    version: str
    app_env: str
    app_name: str
    database_url: str
    secret_key_set: bool


class AllSettingsOut(BaseModel):
    platform: PlatformSettingsOut
    readonly: PlatformReadonlyInfo
