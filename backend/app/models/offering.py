"""Service offerings / packages (产品化专线套餐)."""
from __future__ import annotations

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ServiceType
from app.models.mixins import TimestampMixin


class ServiceOffering(Base, TimestampMixin):
    __tablename__ = "service_offerings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    service_type: Mapped[ServiceType] = mapped_column(
        Enum(ServiceType), default=ServiceType.L2VPN_EVPN
    )
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100)
    sla_target: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cos: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mtu: Mapped[int] = mapped_column(Integer, default=9000)
    # Tier label, e.g. "gold" / "silver" / "bronze".
    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
