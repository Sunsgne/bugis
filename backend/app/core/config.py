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

    # --- Provisioning ---
    # When True, configuration is rendered but NOT pushed to real devices.
    # This lets the whole platform run end-to-end without lab hardware.
    dry_run: bool = True
    netconf_timeout: int = 30

    # --- CORS ---
    cors_origins: list[str] = ["*"]

    # --- Telemetry ---
    enable_metrics: bool = True

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
