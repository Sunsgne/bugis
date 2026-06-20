"""Alarm copy templates — unified titles, details, and outbound notification bodies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.alarm import Alarm
from app.models.enums import AlarmSeverity
from app.services.alarm_template_registry import (
    AlarmTemplates,
    build_kind_copy,
    get_templates,
    kind_meta,
    render_template,
    sample_context,
)


@dataclass(frozen=True)
class AlarmCopy:
    kind: str
    category: str
    priority: str
    title: str
    detail: str
    impact: str
    action: str


_SEVERITY_LABEL: dict[str, str] = {
    "critical": "紧急",
    "major": "重要",
    "minor": "一般",
    "warning": "提示",
    "info": "信息",
}


def kind_label(kind: str, templates: AlarmTemplates | None = None) -> str:
    t = templates or get_templates()
    return t.kind(kind).kind_label


def severity_label(severity: str) -> str:
    return _SEVERITY_LABEL.get(severity, severity.upper())


def _copy_from_kind(
    kind: str,
    context: dict[str, Any],
    templates: AlarmTemplates | None = None,
    *,
    product_name: str = "Bugis",
) -> AlarmCopy:
    t = templates or get_templates()
    k = t.kind(kind)
    ctx = {**context, "product_name": product_name, "priority": k.priority, "category": k.category}
    return AlarmCopy(
        kind=kind,
        category=k.category,
        priority=k.priority,
        title=render_template(k.title, ctx),
        detail=render_template(k.detail, ctx),
        impact=k.impact,
        action=k.action,
    )


def build_circuit_tunnel_down(
    circuit_code: str, status: str, templates: AlarmTemplates | None = None, **extra: Any
) -> AlarmCopy:
    return _copy_from_kind(
        "tunnel_down", {"circuit_code": circuit_code, "status": status, **extra}, templates
    )


def build_circuit_loss(
    circuit_code: str, loss_pct: float, threshold_pct: float,
    templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    return _copy_from_kind(
        "sla_loss",
        {"circuit_code": circuit_code, "loss_pct": loss_pct, "threshold_pct": threshold_pct, **extra},
        templates,
    )


def build_circuit_latency(
    circuit_code: str, latency_ms: float, threshold_ms: float,
    templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    return _copy_from_kind(
        "sla_latency",
        {"circuit_code": circuit_code, "latency_ms": latency_ms, "threshold_ms": threshold_ms, **extra},
        templates,
    )


def build_circuit_utilization(
    circuit_code: str, peak_pct: float, threshold_pct: float,
    templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    return _copy_from_kind(
        "utilization",
        {"circuit_code": circuit_code, "peak_pct": peak_pct, "threshold_pct": threshold_pct, **extra},
        templates,
    )


def build_circuit_health(
    circuit_code: str, score: float, threshold: float,
    templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    return _copy_from_kind(
        "health",
        {"circuit_code": circuit_code, "score": score, "threshold": threshold, **extra},
        templates,
    )


def build_circuit_interruption(
    circuit_code: str, event_detail: str | None, templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    detail = event_detail or "端到端探测判定链路持续中断"
    return _copy_from_kind(
        "circuit_interruption",
        {"circuit_code": circuit_code, "event_detail": detail, **extra},
        templates,
    )


def build_circuit_flap(
    circuit_code: str, flaps: int, window_min: int, templates: AlarmTemplates | None = None, **extra: Any,
) -> AlarmCopy:
    return _copy_from_kind(
        "circuit_flap",
        {"circuit_code": circuit_code, "flaps": flaps, "window_min": window_min, **extra},
        templates,
    )


def build_link_utilization(
    link_name: str,
    util_pct: float,
    threshold_pct: float,
    *,
    capacity_mbps: int,
    traffic_mbps: float,
    templates: AlarmTemplates | None = None,
    **extra: Any,
) -> AlarmCopy:
    cap_g = capacity_mbps / 1000 if capacity_mbps >= 1000 else capacity_mbps
    cap_unit = "Gbps" if capacity_mbps >= 1000 else "Mbps"
    traffic_g = traffic_mbps / 1000 if traffic_mbps >= 1000 else traffic_mbps
    traffic_unit = "Gbps" if traffic_mbps >= 1000 else "Mbps"
    return _copy_from_kind(
        "link_utilization",
        {
            "link_name": link_name,
            "util_pct": util_pct,
            "threshold_pct": threshold_pct,
            "cap_display": f"{cap_g:.0f}{cap_unit}",
            "traffic_display": f"{traffic_g:.1f}{traffic_unit}",
            **extra,
        },
        templates,
    )


def build_test_notification(templates: AlarmTemplates | None = None) -> AlarmCopy:
    return _copy_from_kind("test", {}, templates)


def copy_from_alarm(alarm: Alarm, templates: AlarmTemplates | None = None) -> AlarmCopy:
    t = templates or get_templates()
    meta = kind_meta(t, alarm.kind)
    return AlarmCopy(
        kind=alarm.kind,
        category=meta["category"],
        priority=meta["priority"],
        title=alarm.title,
        detail=alarm.detail or "",
        impact=meta["impact"],
        action=meta["action"],
    )


def _base_context(alarm: Alarm, copy: AlarmCopy, *, product_name: str = "Bugis") -> dict[str, Any]:
    return {
        "product_name": product_name,
        "severity_label": severity_label(alarm.severity.value),
        "severity_upper": alarm.severity.value.upper(),
        "priority": copy.priority,
        "category": copy.category,
        "kind_label": kind_label(alarm.kind),
        "title": copy.title,
    }


def format_notification_text(
    alarm: Alarm,
    *,
    copy: AlarmCopy | None = None,
    templates: AlarmTemplates | None = None,
    product_name: str = "Bugis",
) -> str:
    t = templates or get_templates()
    c = copy or copy_from_alarm(alarm, t)
    g = t.global_
    ctx = _base_context(alarm, c, product_name=product_name)
    lines = [
        render_template(g.banner, ctx),
        render_template(g.meta_line, ctx),
        render_template(g.type_line, {**ctx, "kind_label": kind_label(alarm.kind, t)}),
        "",
        c.title,
        "",
        g.detail_heading,
        f"  {c.detail}",
    ]
    if c.impact:
        lines.extend(["", g.impact_heading, f"  {c.impact}"])
    if c.action:
        lines.extend(["", g.action_heading, f"  {c.action}"])
    if alarm.circuit_id:
        lines.append(f"\n关联专线 ID：{alarm.circuit_id}")
    if alarm.device_id:
        lines.append(f"关联设备 ID：{alarm.device_id}")
    lines.extend(["", render_template(g.footer, ctx)])
    return "\n".join(lines)


def format_notification_payload(
    alarm: Alarm,
    *,
    copy: AlarmCopy | None = None,
    templates: AlarmTemplates | None = None,
) -> dict[str, Any]:
    t = templates or get_templates()
    c = copy or copy_from_alarm(alarm, t)
    return {
        "source": "bugis",
        "severity": alarm.severity.value,
        "severity_label": severity_label(alarm.severity.value),
        "priority": c.priority,
        "category": c.category,
        "kind": alarm.kind,
        "kind_label": kind_label(alarm.kind, t),
        "title": c.title,
        "detail": c.detail,
        "impact": c.impact,
        "action": c.action,
        "circuit_id": alarm.circuit_id,
        "device_id": alarm.device_id,
        "alarm_id": alarm.id,
        "status": alarm.status.value if alarm.status else None,
    }


AUTO_ACK_AFTER_NOTIFY: frozenset[AlarmSeverity] = frozenset({
    AlarmSeverity.MINOR,
    AlarmSeverity.WARNING,
    AlarmSeverity.INFO,
})

AUTO_ACK_ACTOR = "system:auto-notify"
