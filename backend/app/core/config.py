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
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    # --- Device baseline (initialization) defaults ---
    baseline_ntp_server: str = "10.0.0.1"
    baseline_syslog_server: str = "10.0.0.2"
    baseline_snmp_community: str = "bugis-ro"

    # --- Provisioning ---
    # When True, configuration is rendered but NOT pushed to real devices.
    dry_run: bool = False
    netconf_timeout: int = 30
    ssh_timeout: int = 30
    default_netconf_port: int = 830
    default_ssh_port: int = 22
    default_username: str = "admin"

    # --- CORS ---
    cors_origins: list[str] = ["*"]

    # --- Telemetry ---
    enable_metrics: bool = True

    # --- Background scheduler (auto telemetry + alarm evaluation) ---
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 30

    # --- Built-in Bugis SDN controller ---
    controller_bgp_asn: int = 65000
    controller_node_id: str = "bugis-1"

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
