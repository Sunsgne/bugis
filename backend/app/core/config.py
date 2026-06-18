"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object for the platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUGIS_",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "Bugis DCI/EVPN 专线运营平台"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    # Default to SQLite for zero-config local dev; override with PostgreSQL in prod.
    database_url: str = "sqlite:///./bugis.db"
    db_echo: bool = False

    # --- Security / Auth ---
    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    access_token_expire_minutes: int = 60 * 8
    algorithm: str = "HS256"
    expose_openapi: bool = False
    # Comma-separated IPs allowed to set X-Forwarded-For (reverse proxy peers).
    trusted_proxy_ips: list[str] = []
    # Bearer / X-Metrics-Token required for /metrics when set (recommended in prod).
    metrics_token: str = ""
    # Skip validate_production_settings() (tests / local only).
    skip_security_checks: bool = False
    # Verify NETCONF host keys (recommended True in production).
    netconf_hostkey_verify: bool = False

    # --- Device baseline (initialization) defaults ---
    baseline_ntp_server: str = "10.0.0.1"
    baseline_syslog_server: str = "10.0.0.2"
    baseline_snmp_community: str = "bugis-ro"

    # --- Provisioning ---
    # When True, configuration is rendered but NOT pushed to real devices.
    # Defaults to safe dry-run in development; production compose sets false explicitly.
    dry_run: bool = True
    # Explicit opt-in for lab/demo telemetry simulation (never silent in production).
    telemetry_simulation: bool = False
    # Auto-allocated VNI pool start (controller / orchestrator).
    vni_base: int = 30000
    netconf_timeout: int = 30
    ssh_timeout: int = 30
    ssh_read_timeout: int = 120
    default_netconf_port: int = 830
    default_ssh_port: int = 22
    default_username: str = "admin"

    # --- CORS ---
    # Use explicit origins in production; development may use ["*"] without credentials.
    cors_origins: list[str] = []

    # --- Telemetry ---
    enable_metrics: bool = True

    # --- Background scheduler (auto telemetry + alarm evaluation) ---
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 30

    # --- Provisioning concurrency / snapshots ---
    # Capture each target device's live running-config before a circuit
    # apply/teardown (source="pre_change") for diff / rollback / audit.
    snapshot_before_change: bool = True
    # Run provision/teardown work orders on a background worker (queue) instead
    # of inline in the request, so concurrent operators do not block.
    async_provisioning: bool = False
    # Max device pushes the background worker runs in parallel.
    provision_max_concurrency: int = 4
    # How often the worker reconciles orphaned queued work orders (seconds).
    worker_poll_seconds: int = 5
    # Background provisioning worker (disable on HA follower nodes).
    worker_enabled: bool = True

    # --- Container / HA bootstrap (production multi-node) ---
    run_migrations: bool = True
    run_seed: bool = True
    run_demo: bool = True

    # --- Built-in Bugis SDN controller ---
    controller_bgp_asn: int = 65000
    controller_node_id: str = "bugis-1"
    # Skip VNI/VSI already present on devices when auto-allocating new circuits.
    smart_overlay_allocation: bool = True

    # --- Alarm thresholds (SLA / capacity) ---
    threshold_packet_loss_pct: float = 0.5
    threshold_latency_ms: float = 50.0
    threshold_utilization_pct: float = 90.0
    threshold_health_score: float = 70.0
    # Capacity reservation warning ratio for links.
    threshold_link_utilization_pct: float = 85.0

    # --- Bootstrap admin ---
    first_superuser: str = "admin"
    first_superuser_password: str = "admin123"

    # --- Northbound integration ---
    # Shared token for StackStorm-style webhook intake (X-Webhook-Token header).
    webhook_token: str = "bugis-webhook-token"

    # --- Email (SMTP) for email notification channels ---
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "bugis@localhost"
    smtp_provider: str = ""
    smtp_security: str = "starttls"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
