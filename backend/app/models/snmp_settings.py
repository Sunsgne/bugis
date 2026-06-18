"""Global SNMP discovery / polling settings (singleton row)."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class SnmpSettings(Base, TimestampMixin):
    """Platform-wide SNMP parameters used by interface discovery and checks."""

    __tablename__ = "snmp_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    version: Mapped[str] = mapped_column(String(8), default="2c")  # 2c | 3

    # SNMPv2c
    community: Mapped[str] = mapped_column(String(512), default="bugis-ro")
    write_community: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Transport
    port: Mapped[int] = mapped_column(Integer, default=161)
    timeout_sec: Mapped[float] = mapped_column(Float, default=2.0)
    retries: Mapped[int] = mapped_column(Integer, default=1)
    max_repetitions: Mapped[int] = mapped_column(Integer, default=25)

    # Credential precedence: device.password overrides global community when set.
    prefer_device_community: Mapped[bool] = mapped_column(Boolean, default=True)

    # IF-MIB walks
    walk_if_descr: Mapped[bool] = mapped_column(Boolean, default=True)
    walk_if_alias: Mapped[bool] = mapped_column(Boolean, default=True)
    walk_if_high_speed: Mapped[bool] = mapped_column(Boolean, default=True)
    walk_if_oper_status: Mapped[bool] = mapped_column(Boolean, default=True)

    # Post-discovery behavior
    sync_link_capacity: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_discover_on_check: Mapped[bool] = mapped_column(Boolean, default=False)

    # Filter interface names (regex strings)
    exclude_name_patterns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    include_name_patterns: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # SNMPv3 USM
    v3_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    v3_security_level: Mapped[str] = mapped_column(
        String(16), default="authPriv"
    )  # noAuthNoPriv | authNoPriv | authPriv
    v3_auth_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    v3_auth_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    v3_priv_protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    v3_priv_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    v3_context_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Pushed into device baseline template (init config)
    baseline_community: Mapped[str] = mapped_column(String(512), default="bugis-ro")

    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
