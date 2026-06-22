"""Three-layer forwarding path API schemas."""
from __future__ import annotations

from pydantic import BaseModel


class ForwardingPathHop(BaseModel):
    sequence: int
    layer: str | None = None
    device_id: int | None = None
    device_name: str | None = None
    detail: str | None = None


class ForwardingPathResponse(BaseModel):
    circuit_id: int
    circuit_code: str
    path_mode: str
    generated_at: str
    business_plane: dict
    control_plane: dict
    underlay: dict
