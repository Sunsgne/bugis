"""SDN / vendor fabric controllers for northbound delegation."""
from __future__ import annotations

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ControllerType
from app.models.mixins import TimestampMixin


class Controller(Base, TimestampMixin):
    __tablename__ = "controllers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[ControllerType] = mapped_column(Enum(ControllerType))
    base_url: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NOTE: store credentials in a vault in production.
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verify_tls: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
