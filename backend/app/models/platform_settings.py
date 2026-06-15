"""Platform-wide runtime settings (singleton row, persisted in DB)."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PlatformSettings(Base, TimestampMixin):
    """Editable operational parameters (mirrors env defaults, overridable at runtime)."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    netconf_timeout: Mapped[int] = mapped_column(Integer, default=30)

    baseline_ntp_server: Mapped[str] = mapped_column(String(64), default="10.0.0.1")
    baseline_syslog_server: Mapped[str] = mapped_column(String(64), default="10.0.0.2")

    scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scheduler_interval_seconds: Mapped[int] = mapped_column(Integer, default=30)

    threshold_packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.5)
    threshold_latency_ms: Mapped[float] = mapped_column(Float, default=50.0)
    threshold_utilization_pct: Mapped[float] = mapped_column(Float, default=90.0)
    threshold_health_score: Mapped[float] = mapped_column(Float, default=70.0)
    threshold_link_utilization_pct: Mapped[float] = mapped_column(Float, default=85.0)

    controller_bgp_asn: Mapped[int] = mapped_column(Integer, default=65000)
    controller_node_id: Mapped[str] = mapped_column(String(64), default="bugis-1")

    webhook_token: Mapped[str] = mapped_column(String(128), default="bugis-webhook-token")

    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=25)
    smtp_user: Mapped[str] = mapped_column(String(128), default="")
    smtp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_from: Mapped[str] = mapped_column(String(255), default="bugis@localhost")
    smtp_provider: Mapped[str] = mapped_column(String(64), default="")
    smtp_security: Mapped[str] = mapped_column(String(16), default="starttls")

    enable_metrics: Mapped[bool] = mapped_column(Boolean, default=True)

    access_token_expire_minutes: Mapped[int] = mapped_column(Integer, default=60 * 24)

    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
