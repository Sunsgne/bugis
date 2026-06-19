"""Editable alarm notification templates — defaults, merge, and {{var}} rendering."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

KIND_KEYS = (
    "tunnel_down",
    "circuit_interruption",
    "sla_loss",
    "sla_latency",
    "utilization",
    "health",
    "circuit_flap",
    "link_utilization",
    "test",
)

GLOBAL_KEYS = (
    "banner",
    "footer",
    "email_subject",
    "detail_heading",
    "impact_heading",
    "action_heading",
    "meta_line",
    "type_line",
)

_CACHE: dict[str, Any] | None = None
_CACHE_VERSION = 0


def bump_cache() -> None:
    global _CACHE, _CACHE_VERSION
    _CACHE = None
    _CACHE_VERSION += 1


def render_template(template: str, context: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        val = context.get(key)
        if val is None:
            return match.group(0)
        if isinstance(val, float):
            if key.endswith("_pct") or "pct" in key:
                return f"{val:.3f}".rstrip("0").rstrip(".")
            return f"{val:.1f}".rstrip("0").rstrip(".")
        return str(val)

    return _VAR_RE.sub(repl, template)


@dataclass
class KindTemplate:
    kind_label: str
    category: str
    priority: str
    title: str
    detail: str
    impact: str
    action: str


@dataclass
class GlobalTemplate:
    banner: str
    footer: str
    email_subject: str
    detail_heading: str
    impact_heading: str
    action_heading: str
    meta_line: str
    type_line: str
    html_enabled: bool = True


@dataclass
class AlarmTemplates:
    global_: GlobalTemplate
    kinds: dict[str, KindTemplate]
    version: int = 0

    def kind(self, kind: str) -> KindTemplate:
        return self.kinds.get(kind) or self.kinds["test"]


def _default_global() -> dict[str, Any]:
    return {
        "banner": "━━━━━━━━ {{product_name}} 智能运维告警 ━━━━━━━━",
        "footer": "— 本消息由 {{product_name}} 平台自动发送 —",
        "email_subject": "[{{product_name}}][{{severity_label}}] {{title}}",
        "detail_heading": "▎详情",
        "impact_heading": "▎影响评估",
        "action_heading": "▎建议处置",
        "meta_line": "级别：{{severity_label}} ({{severity_upper}}) · {{priority}} · {{category}}",
        "type_line": "类型：{{kind_label}}",
        "html_enabled": True,
    }


def _default_kinds() -> dict[str, dict[str, str]]:
    return {
        "tunnel_down": {
            "kind_label": "隧道异常",
            "category": "业务可用性",
            "priority": "P1",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 隧道状态异常",
            "detail": "当前状态：{{status}} · 平台判定业务隧道不可用或处于降级态",
            "impact": "专线隧道或业务状态异常，业务可能中断或处于降级运行。",
            "action": "立即登录平台核查专线状态、隧道探测结果与近期变更工单。",
        },
        "circuit_interruption": {
            "kind_label": "业务中断",
            "category": "业务可用性",
            "priority": "P1",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 业务中断",
            "detail": "{{event_detail}}",
            "impact": "端到端链路持续中断，客户业务不可用。",
            "action": "启动应急处置：核查 PE 隧道、BGP EVPN 会话与 underlay 可达性。",
        },
        "sla_loss": {
            "kind_label": "丢包超标",
            "category": "SLA 质量",
            "priority": "P2",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 丢包率越限",
            "detail": "实测丢包 {{loss_pct}}% · SLA 阈值 {{threshold_pct}}% · 超出承诺区间",
            "impact": "丢包率超出 SLA 承诺区间，实时业务体验可能下降。",
            "action": "结合流量峰值与路径探测，排查拥塞、误码或 overlay 异常。",
        },
        "sla_latency": {
            "kind_label": "时延超标",
            "category": "SLA 质量",
            "priority": "P3",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 时延越限",
            "detail": "实测时延 {{latency_ms}} ms · SLA 阈值 {{threshold_ms}} ms",
            "impact": "端到端时延超出设定阈值，时敏业务可能受影响。",
            "action": "对比近 24h 时延曲线，排查路径绕路、队列拥塞或探测异常。",
        },
        "utilization": {
            "kind_label": "带宽拥塞",
            "category": "容量规划",
            "priority": "P3",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 峰值利用率偏高",
            "detail": "峰值利用率 {{peak_pct}}% · 告警阈值 {{threshold_pct}}% · 建议关注扩容窗口",
            "impact": "专线峰值带宽利用率偏高，存在拥塞隐患。",
            "action": "结合月 95 计费与业务增长预测，提前规划带宽升级。",
        },
        "health": {
            "kind_label": "健康劣化",
            "category": "综合健康",
            "priority": "P2",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 健康评分偏低",
            "detail": "综合健康分 {{score}} · 下限阈值 {{threshold}}",
            "impact": "综合健康评分偏低，多项 QoS 指标存在劣化风险。",
            "action": "在监控面板查看时延、丢包、利用率明细，评估是否需要优化或扩容。",
        },
        "circuit_flap": {
            "kind_label": "闪断频繁",
            "category": "链路稳定性",
            "priority": "P2",
            "title": "【{{priority}}·{{category}}】专线 {{circuit_code}} 闪断频繁",
            "detail": "近 {{window_min}} 分钟内闪断 {{flaps}} 次 · 超过稳定性阈值",
            "impact": "短时中断频繁出现，存在闪断或控制面震荡风险。",
            "action": "检查物理链路、BFD/隧道保活与近期割接窗口是否重叠。",
        },
        "link_utilization": {
            "kind_label": "骨干拥塞",
            "category": "容量规划",
            "priority": "P2",
            "title": "【{{priority}}·{{category}}】骨干链路 {{link_name}} 利用率越限",
            "detail": "峰值利用率 {{util_pct}}% · 阈值 {{threshold_pct}}% · 合同带宽 {{cap_display}} · 峰值流量 {{traffic_display}}",
            "impact": "骨干链路利用率逼近容量上限，可能出现拥塞与 SLA 劣化。",
            "action": "评估带宽扩容、流量调度或路径优化，关注峰值时段趋势。",
        },
        "test": {
            "kind_label": "测试通知",
            "category": "系统自检",
            "priority": "—",
            "title": "【系统自检】{{product_name}} 告警通知渠道联通测试",
            "detail": "若您收到此消息，说明通知渠道配置正确，可正常投递生产告警。",
            "impact": "这是一条测试通知，不代表真实故障。",
            "action": "无需处理；若误收请检查通知渠道配置。",
        },
    }


def default_templates_dict() -> dict[str, Any]:
    return {"global": _default_global(), "kinds": _default_kinds()}


def _parse_stored(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def merge_templates(custom: dict[str, Any] | None) -> AlarmTemplates:
    base = default_templates_dict()
    if custom:
        g = custom.get("global") or {}
        for k in GLOBAL_KEYS:
            if k in g and g[k] is not None:
                base["global"][k] = g[k]
        if "html_enabled" in g:
            base["global"]["html_enabled"] = bool(g["html_enabled"])
        kinds_in = custom.get("kinds") or {}
        for kind, tpl in kinds_in.items():
            if kind not in base["kinds"] or not isinstance(tpl, dict):
                continue
            for fk in ("kind_label", "category", "priority", "title", "detail", "impact", "action"):
                if fk in tpl and tpl[fk] is not None:
                    base["kinds"][kind][fk] = tpl[fk]

    g = base["global"]
    global_tpl = GlobalTemplate(
        banner=g["banner"],
        footer=g["footer"],
        email_subject=g["email_subject"],
        detail_heading=g["detail_heading"],
        impact_heading=g["impact_heading"],
        action_heading=g["action_heading"],
        meta_line=g["meta_line"],
        type_line=g["type_line"],
        html_enabled=bool(g.get("html_enabled", True)),
    )
    kinds: dict[str, KindTemplate] = {}
    for kind, row in base["kinds"].items():
        kinds[kind] = KindTemplate(**row)
    return AlarmTemplates(global_=global_tpl, kinds=kinds, version=_CACHE_VERSION)


def get_templates(db: Session | None = None) -> AlarmTemplates:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    custom: dict[str, Any] = {}
    if db is not None:
        from app.services.platform_settings import get_or_create

        row = get_or_create(db)
        custom = _parse_stored(getattr(row, "alarm_notification_templates", None))

    merged = merge_templates(custom)
    if db is None:
        return merged
    _CACHE = merged
    return merged


def save_templates(db: Session, payload: dict[str, Any]) -> AlarmTemplates:
    from app.services.platform_settings import get_or_create

    row = get_or_create(db)
    row.alarm_notification_templates = json.dumps(payload, ensure_ascii=False)
    db.commit()
    db.refresh(row)
    bump_cache()
    return get_templates(db)


def reset_templates(db: Session) -> AlarmTemplates:
    from app.services.platform_settings import get_or_create

    row = get_or_create(db)
    row.alarm_notification_templates = None
    db.commit()
    db.refresh(row)
    bump_cache()
    return get_templates(db)


def templates_to_dict(templates: AlarmTemplates) -> dict[str, Any]:
    return {
        "global": {
            "banner": templates.global_.banner,
            "footer": templates.global_.footer,
            "email_subject": templates.global_.email_subject,
            "detail_heading": templates.global_.detail_heading,
            "impact_heading": templates.global_.impact_heading,
            "action_heading": templates.global_.action_heading,
            "meta_line": templates.global_.meta_line,
            "type_line": templates.global_.type_line,
            "html_enabled": templates.global_.html_enabled,
        },
        "kinds": {
            k: {
                "kind_label": v.kind_label,
                "category": v.category,
                "priority": v.priority,
                "title": v.title,
                "detail": v.detail,
                "impact": v.impact,
                "action": v.action,
            }
            for k, v in templates.kinds.items()
        },
    }


def kind_meta(templates: AlarmTemplates, kind: str) -> dict[str, str]:
    k = templates.kind(kind)
    return {
        "kind_label": k.kind_label,
        "category": k.category,
        "priority": k.priority,
        "impact": k.impact,
        "action": k.action,
    }


def build_kind_copy(
    templates: AlarmTemplates,
    kind: str,
    context: dict[str, Any],
    *,
    product_name: str = "Bugis",
) -> tuple[str, str, str, str, str, str]:
    """Returns kind, category, priority, title, detail, impact, action — as rendered strings."""
    k = templates.kind(kind)
    ctx = {**context, "product_name": product_name, "priority": k.priority, "category": k.category}
    title = render_template(k.title, ctx)
    detail = render_template(k.detail, ctx)
    return kind, k.category, k.priority, title, detail, k.impact, k.action


VARIABLE_CATALOG: dict[str, list[dict[str, str]]] = {
    "global": [
        {"key": "product_name", "label": "产品名称"},
        {"key": "severity_label", "label": "级别中文"},
        {"key": "severity_upper", "label": "级别英文大写"},
        {"key": "kind_label", "label": "告警类型"},
        {"key": "priority", "label": "优先级 P1/P2/P3"},
        {"key": "category", "label": "分类"},
        {"key": "title", "label": "告警标题"},
    ],
    "tunnel_down": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "status", "label": "当前状态"},
    ],
    "circuit_interruption": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "event_detail", "label": "事件详情"},
    ],
    "sla_loss": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "loss_pct", "label": "实测丢包 %"},
        {"key": "threshold_pct", "label": "阈值 %"},
    ],
    "sla_latency": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "latency_ms", "label": "实测时延 ms"},
        {"key": "threshold_ms", "label": "阈值 ms"},
    ],
    "utilization": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "peak_pct", "label": "峰值利用率 %"},
        {"key": "threshold_pct", "label": "阈值 %"},
    ],
    "health": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "score", "label": "健康分"},
        {"key": "threshold", "label": "下限阈值"},
    ],
    "circuit_flap": [
        {"key": "circuit_code", "label": "专线编码"},
        {"key": "flaps", "label": "闪断次数"},
        {"key": "window_min", "label": "统计窗口(分钟)"},
    ],
    "link_utilization": [
        {"key": "link_name", "label": "链路名称"},
        {"key": "util_pct", "label": "利用率 %"},
        {"key": "threshold_pct", "label": "阈值 %"},
        {"key": "cap_display", "label": "合同带宽"},
        {"key": "traffic_display", "label": "峰值流量"},
    ],
    "test": [{"key": "product_name", "label": "产品名称"}],
}


def sample_context(kind: str) -> dict[str, Any]:
    samples: dict[str, dict[str, Any]] = {
        "tunnel_down": {"circuit_code": "CIR-09AAF4", "status": "degraded"},
        "circuit_interruption": {
            "circuit_code": "CIR-09AAF4",
            "event_detail": "端到端探测判定链路持续中断",
        },
        "sla_loss": {"circuit_code": "CIR-09AAF4", "loss_pct": 1.25, "threshold_pct": 0.5},
        "sla_latency": {"circuit_code": "CIR-09AAF4", "latency_ms": 68.2, "threshold_ms": 50},
        "utilization": {"circuit_code": "CIR-09AAF4", "peak_pct": 92.4, "threshold_pct": 90},
        "health": {"circuit_code": "CIR-09AAF4", "score": 62.5, "threshold": 70},
        "circuit_flap": {"circuit_code": "CIR-09AAF4", "flaps": 4, "window_min": 15},
        "link_utilization": {
            "link_name": "SG-HK-01",
            "util_pct": 88.2,
            "threshold_pct": 85,
            "cap_display": "10Gbps",
            "traffic_display": "8.8Gbps",
        },
        "test": {},
    }
    return deepcopy(samples.get(kind, {}))
