"""Tenants (customers) for multi-tenant / hybrid-cloud access."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TenantStatus, TenantType
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.circuit import Circuit


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    type: Mapped[TenantType] = mapped_column(
        str_enum_column(TenantType), default=TenantType.ENTERPRISE
    )
    status: Mapped[TenantStatus] = mapped_column(
        str_enum_column(TenantStatus), default=TenantStatus.ACTIVE
    )
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Optional cloud account / VPC reference for hybrid-cloud access.
    cloud_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    circuits: Mapped[list["Circuit"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
