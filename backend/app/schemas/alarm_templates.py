"""Alarm notification template schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class KindTemplateIn(BaseModel):
    kind_label: str = Field(max_length=64)
    category: str = Field(max_length=64)
    priority: str = Field(max_length=16)
    title: str = Field(max_length=512)
    detail: str = Field(max_length=1024)
    impact: str = Field(max_length=1024)
    action: str = Field(max_length=1024)


class GlobalTemplateIn(BaseModel):
    banner: str = Field(max_length=256)
    footer: str = Field(max_length=256)
    email_subject: str = Field(max_length=256)
    detail_heading: str = Field(max_length=64)
    impact_heading: str = Field(max_length=64)
    action_heading: str = Field(max_length=64)
    meta_line: str = Field(max_length=256)
    type_line: str = Field(max_length=128)
    html_enabled: bool = True


class AlarmTemplatesIn(BaseModel):
    global_: GlobalTemplateIn = Field(alias="global")
    kinds: dict[str, KindTemplateIn]

    model_config = {"populate_by_name": True}


class VariableDef(BaseModel):
    key: str
    label: str


class AlarmTemplatesOut(BaseModel):
    global_: GlobalTemplateIn = Field(alias="global")
    kinds: dict[str, KindTemplateIn]
    defaults: dict
    variables: dict[str, list[VariableDef]]
    kinds_order: list[str]

    model_config = {"populate_by_name": True}


class AlarmTemplatePreviewIn(BaseModel):
    kind: str = "sla_loss"
    severity: str = "major"
    product_name: str | None = None


class AlarmTemplatePreviewOut(BaseModel):
    text: str
    html: str
    subject: str
    title: str
