"""Alarm notification template editor API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.alarm import Alarm
from app.models.enums import AlarmSeverity, AlarmStatus
from app.models.user import User
from app.schemas.alarm_templates import (
    AlarmTemplatePreviewIn,
    AlarmTemplatePreviewOut,
    AlarmTemplatesIn,
    AlarmTemplatesOut,
    GlobalTemplateIn,
    KindTemplateIn,
    VariableDef,
)
from app.services import alarm_messages as msg
from app.services.alarm_email_templates import render_alarm_email
from app.services.alarm_template_registry import (
    KIND_KEYS,
    VARIABLE_CATALOG,
    default_templates_dict,
    get_templates,
    render_template,
    reset_templates,
    sample_context,
    save_templates,
    templates_to_dict,
)
from app.services.platform_settings import get_or_create

router = APIRouter()


def _preview_copy(kind: str, templates):
    ctx = sample_context(kind)
    builders = {
        "tunnel_down": lambda: msg.build_circuit_tunnel_down(
            ctx.get("circuit_code", "CIR-PREVIEW"), str(ctx.get("status", "degraded")), templates, **ctx
        ),
        "circuit_interruption": lambda: msg.build_circuit_interruption(
            str(ctx.get("circuit_code", "CIR-PREVIEW")), ctx.get("event_detail"), templates, **ctx
        ),
        "sla_loss": lambda: msg.build_circuit_loss(
            str(ctx.get("circuit_code", "CIR-PREVIEW")),
            float(ctx.get("loss_pct", 1.25)),
            float(ctx.get("threshold_pct", 0.5)),
            templates,
            **ctx,
        ),
        "sla_latency": lambda: msg.build_circuit_latency(
            str(ctx.get("circuit_code", "CIR-PREVIEW")),
            float(ctx.get("latency_ms", 68.2)),
            float(ctx.get("threshold_ms", 50.0)),
            templates,
            **ctx,
        ),
        "utilization": lambda: msg.build_circuit_utilization(
            str(ctx.get("circuit_code", "CIR-PREVIEW")),
            float(ctx.get("peak_pct", 92.4)),
            float(ctx.get("threshold_pct", 90.0)),
            templates,
            **ctx,
        ),
        "health": lambda: msg.build_circuit_health(
            str(ctx.get("circuit_code", "CIR-PREVIEW")),
            float(ctx.get("score", 62.5)),
            float(ctx.get("threshold", 70.0)),
            templates,
            **ctx,
        ),
        "circuit_flap": lambda: msg.build_circuit_flap(
            str(ctx.get("circuit_code", "CIR-PREVIEW")),
            int(ctx.get("flaps", 4)),
            int(ctx.get("window_min", 15)),
            templates,
            **ctx,
        ),
        "link_utilization": lambda: msg.build_link_utilization(
            str(ctx.get("link_name", "SG-HK-01")),
            float(ctx.get("util_pct", 88.2)),
            float(ctx.get("threshold_pct", 85.0)),
            capacity_mbps=int(ctx.get("capacity_mbps", 10000)),
            traffic_mbps=8800.0,
            templates=templates,
            **ctx,
        ),
        "test": lambda: msg.build_test_notification(templates),
    }
    return builders.get(kind, builders["sla_loss"])()


def _to_out(templates) -> AlarmTemplatesOut:
    d = templates_to_dict(templates)
    return AlarmTemplatesOut(
        global_=GlobalTemplateIn(**d["global"]),
        kinds={k: KindTemplateIn(**v) for k, v in d["kinds"].items()},
        defaults=default_templates_dict(),
        variables={
            k: [VariableDef(**v) for v in rows]
            for k, rows in VARIABLE_CATALOG.items()
        },
        kinds_order=list(KIND_KEYS),
    )


@router.get("", response_model=AlarmTemplatesOut)
def get_alarm_templates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return _to_out(get_templates(db))


@router.put("", response_model=AlarmTemplatesOut)
def update_alarm_templates(
    payload: AlarmTemplatesIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    data = payload.model_dump(by_alias=True)
    saved = save_templates(db, data)
    return _to_out(saved)


@router.post("/reset", response_model=AlarmTemplatesOut)
def reset_alarm_templates(
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    return _to_out(reset_templates(db))


@router.post("/preview", response_model=AlarmTemplatePreviewOut)
def preview_alarm_template(
    body: AlarmTemplatePreviewIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    plat = get_or_create(db)
    product = body.product_name or plat.product_name or "Bugis Network"
    templates = get_templates(db)
    copy = _preview_copy(body.kind, templates)
    alarm = Alarm(
        kind=body.kind,
        severity=AlarmSeverity(body.severity),
        status=AlarmStatus.ACTIVE,
        title=copy.title,
        detail=copy.detail,
        dedup_key="preview",
        circuit_id=1,
    )
    text = msg.format_notification_text(alarm, copy=copy, templates=templates, product_name=product)
    html = render_alarm_email(plat, alarm, copy=copy, templates=templates, plain_body=text)
    ctx = {
        "product_name": product,
        "severity_label": msg.severity_label(body.severity),
        "title": copy.title,
    }
    subject = render_template(templates.global_.email_subject, ctx)
    return AlarmTemplatePreviewOut(text=text, html=html, subject=subject, title=copy.title)
