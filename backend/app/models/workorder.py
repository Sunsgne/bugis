"""Work orders (工单) orchestrating circuit lifecycle changes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import WorkOrderStatus, WorkOrderType
from app.models.mixins import TimestampMixin, str_enum_column

if TYPE_CHECKING:
    from app.models.circuit import Circuit
    from app.models.config_job import ConfigJob


class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    # Retained when the circuit row is deleted (audit / billing trail).
    circuit_code: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    circuit_id: Mapped[int | None] = mapped_column(
        ForeignKey("circuits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[WorkOrderType] = mapped_column(
        str_enum_column(WorkOrderType), default=WorkOrderType.PROVISION
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        str_enum_column(WorkOrderStatus), default=WorkOrderStatus.DRAFT
    )
    title: Mapped[str] = mapped_column(String(255))
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Free-form JSON-ish payload describing requested change parameters.
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    circuit: Mapped["Circuit | None"] = relationship(back_populates="work_orders")
    events: Mapped[list["WorkOrderEvent"]] = relationship(
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderEvent.id",
    )
    config_jobs: Mapped[list["ConfigJob"]] = relationship(
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="ConfigJob.id",
    )


class WorkOrderEvent(Base, TimestampMixin):
    """Audit-trail event in a work order's lifecycle."""

    __tablename__ = "work_order_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)

    work_order: Mapped["WorkOrder"] = relationship(back_populates="events")
