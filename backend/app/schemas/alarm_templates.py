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


class GlobalTemplatePatch(BaseModel):
    """Partial global template overlay for live preview (unspecified fields keep saved values)."""

    banner: str | None = None
    footer: str | None = None
    email_subject: str | None = None
    detail_heading: str | None = None
    impact_heading: str | None = None
    action_heading: str | None = None
    meta_line: str | None = None
    type_line: str | None = None
    html_enabled: bool | None = None


class KindTemplatePatch(BaseModel):
    """Partial kind template overlay for live preview."""

    kind_label: str | None = None
    category: str | None = None
    priority: str | None = None
    title: str | None = None
    detail: str | None = None
    impact: str | None = None
    action: str | None = None


class AlarmTemplatePreviewIn(BaseModel):
    kind: str = "sla_loss"
    severity: str = "major"
    product_name: str | None = None
    global_: GlobalTemplatePatch | None = Field(default=None, alias="global")
    kinds: dict[str, KindTemplatePatch] | None = None

    model_config = {"populate_by_name": True}


class AlarmTemplatePreviewOut(BaseModel):
    text: str
    html: str
    subject: str
    title: str
