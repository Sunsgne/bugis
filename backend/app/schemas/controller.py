"""Controller schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.ip_validation import validate_ip_address
from app.core.url_validation import validate_controller_base_url
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

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        return validate_controller_base_url(v)


class ControllerCreate(ControllerBase):
    pass


class ControllerUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    verify_tls: int | None = None
    description: str | None = None

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_controller_base_url(v)


class ControllerOut(ControllerBase, TimestampedSchema):
    id: int
    password: str | None = Field(default=None, exclude=True)
