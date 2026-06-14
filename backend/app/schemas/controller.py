"""Controller schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ControllerType
from app.schemas.common import TimestampedSchema


class ControllerBase(BaseModel):
    name: str
    type: ControllerType
    base_url: str
    username: str | None = None
    password: str | None = None
    verify_tls: int = 0
    description: str | None = None


class ControllerCreate(ControllerBase):
    pass


class ControllerUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    verify_tls: int | None = None
    description: str | None = None


class ControllerOut(ControllerBase, TimestampedSchema):
    id: int
    password: str | None = Field(default=None, exclude=True)
