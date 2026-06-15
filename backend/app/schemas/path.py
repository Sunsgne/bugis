"""Path preview / validation schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import PathMode


class PathHopOut(BaseModel):
    device_id: int
    name: str
    role: str
    overlay_tech: str
    sr_node_sid: int | None = None
    hop_type: str


class PathPreviewRequest(BaseModel):
    endpoint_device_ids: list[int] = Field(..., min_length=2)
    via_device_ids: list[int] = Field(default_factory=list)
    path_mode: PathMode = PathMode.AUTO


class PathPreviewResponse(BaseModel):
    path_mode: str
    explicit_supported: bool
    reason: str | None = None
    hops: list[PathHopOut] = []
    segment_list: list[int] = []
    connectivity_errors: list[str] = []


class CircuitPathHopOut(BaseModel):
    device_id: int
    sequence: int
    device_name: str | None = None
    overlay_tech: str | None = None
    sr_node_sid: int | None = None
