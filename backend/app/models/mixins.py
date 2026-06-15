"""Reusable model mixins."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column

E = TypeVar("E", bound=Enum)


def str_enum_column(enum_cls: type[E], **kwargs) -> SAEnum:
    """Persist str enums by value (e.g. dot1q) for SQLite compatibility."""
    return SAEnum(
        enum_cls,
        values_callable=lambda obj: [member.value for member in obj],
        native_enum=False,
        validate_strings=True,
        length=max(len(member.value) for member in enum_cls) + 8,
        **kwargs,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
