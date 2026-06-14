"""Shared schema helpers."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base schema that reads attributes from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedSchema(ORMModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Message(BaseModel):
    detail: str
