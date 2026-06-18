"""Alarm copy templates — unified titles, details, and outbound notification bodies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.alarm import Alarm
from app.models.enums import AlarmSeverity


@dataclass(frozen=True)
class AlarmCopy:
    kind: str
    category: str
    priority: str
    title: str
    detail: str
    impact: str
    action: str


_KIND_META: dict[str, dict[str, str]] = {
    "tunnel_down": {
        "category": "业务可用性",
        "priority": "P1",
        "impact": "专线隧道或业务状态异常，业务可能中断或处于降级运行。",
        "action": "立即登录平台核查专线状态、隧道探测结果与近期变更工单。",
    },
    "circuit_interruption": {
        "category": "业务可用性",
        "priority": "P1",
        "impact": "端到端链路持续中断，客户业务不可用。",
        "action": "启动应急处置：核查 PE 隧道、BGP EVPN 会话与 underlay 可达性。",
    },
    "sla_loss": {
        "category": "SLA 质量",
        "priority": "P2",
        "impact": "丢包率超出 SLA 承诺区间，实时业务体验可能下降。",
        "action": "结合流量峰值与路径探测，排查拥塞、误码或 overlay 异常。",
    },
    "health": {
        "category": "综合健康",
        "priority": "P2",
        "impact": "综合健康评分偏低，多项 QoS 指标存在劣化风险。",
        "action": "在监控面板查看时延、丢包、利用率明细，评估是否需要优化或扩容。",
    },
    "circuit_flap": {
        "category": "链路稳定性",
        "priority": "P2",
        "impact": "短时中断频繁出现，存在闪断或控制面震荡风险。",
        "action": "检查物理链路、BFD/隧道保活与近期割接窗口是否重叠。",
    },
    "link_utilization": {
        "category": "容量规划",
        "priority": "P2",
        "impact": "骨干链路利用率逼近容量上限，可能出现拥塞与 SLA 劣化。",
        "action": "评估带宽扩容、流量调度或路径优化，关注峰值时段趋势。",
    },
    "sla_latency": {
        "category": "SLA 质量",
        "priority": "P3",
        "impact": "端到端时延超出设定阈值，时敏业务可能受影响。",
        "action": "对比近 24h 时延曲线，排查路径绕路、队列拥塞或探测异常。",
    },
    "utilization": {
        "category": "容量规划",
        "priority": "P3",
        "impact": "专线峰值带宽利用率偏高，存在拥塞隐患。",
        "action": "结合月 95 计费与业务增长预测，提前规划带宽升级。",
    },
    "test": {
        "category": "系统自检",
        "priority": "—",
        "impact": "这是一条测试通知，不代表真实故障。",
        "action": "无需处理；若误收请检查通知渠道配置。",
    },
}

_SEVERITY_LABEL: dict[str, str] = {
    "critical": "紧急",
    "major": "重要",
    "minor": "一般",
    "warning": "提示",
    "info": "信息",
}


def kind_label(kind: str) -> str:
    return {
        "tunnel_down": "隧道异常",
        "circuit_interruption": "业务中断",
        "sla_loss": "丢包超标",
        "sla_latency": "时延超标",
        "utilization": "带宽拥塞",
        "health": "健康劣化",
        "circuit_flap": "闪断频繁",
        "link_utilization": "骨干拥塞",
        "test": "测试通知",
    }.get(kind, kind)


def severity_label(severity: str) -> str:
    return _SEVERITY_LABEL.get(severity, severity.upper())


def build_circuit_tunnel_down(circuit_code: str, status: str) -> AlarmCopy:
    meta = _KIND_META["tunnel_down"]
    return AlarmCopy(
        kind="tunnel_down",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 隧道状态异常",
        detail=f"当前状态：{status} · 平台判定业务隧道不可用或处于降级态",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_loss(circuit_code: str, loss_pct: float, threshold_pct: float) -> AlarmCopy:
    meta = _KIND_META["sla_loss"]
    return AlarmCopy(
        kind="sla_loss",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 丢包率越限",
        detail=f"实测丢包 {loss_pct:.3f}% · SLA 阈值 {threshold_pct}% · 超出承诺区间",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_latency(circuit_code: str, latency_ms: float, threshold_ms: float) -> AlarmCopy:
    meta = _KIND_META["sla_latency"]
    return AlarmCopy(
        kind="sla_latency",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 时延越限",
        detail=f"实测时延 {latency_ms:.1f} ms · SLA 阈值 {threshold_ms:.0f} ms",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_utilization(circuit_code: str, peak_pct: float, threshold_pct: float) -> AlarmCopy:
    meta = _KIND_META["utilization"]
    return AlarmCopy(
        kind="utilization",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 峰值利用率偏高",
        detail=f"峰值利用率 {peak_pct:.1f}% · 告警阈值 {threshold_pct}% · 建议关注扩容窗口",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_health(circuit_code: str, score: float, threshold: float) -> AlarmCopy:
    meta = _KIND_META["health"]
    return AlarmCopy(
        kind="health",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 健康评分偏低",
        detail=f"综合健康分 {score:.1f} · 下限阈值 {threshold:.0f}",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_interruption(circuit_code: str, event_detail: str | None) -> AlarmCopy:
    meta = _KIND_META["circuit_interruption"]
    detail = event_detail or "端到端探测判定链路持续中断"
    return AlarmCopy(
        kind="circuit_interruption",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 业务中断",
        detail=detail,
        impact=meta["impact"],
        action=meta["action"],
    )


def build_circuit_flap(circuit_code: str, flaps: int, window_min: int) -> AlarmCopy:
    meta = _KIND_META["circuit_flap"]
    return AlarmCopy(
        kind="circuit_flap",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】专线 {circuit_code} 闪断频繁",
        detail=f"近 {window_min} 分钟内闪断 {flaps} 次 · 超过稳定性阈值",
        impact=meta["impact"],
        action=meta["action"],
    )


def build_link_utilization(
    link_name: str,
    util_pct: float,
    threshold_pct: float,
    *,
    capacity_mbps: int,
    traffic_mbps: float,
) -> AlarmCopy:
    meta = _KIND_META["link_utilization"]
    cap_g = capacity_mbps / 1000 if capacity_mbps >= 1000 else capacity_mbps
    cap_unit = "Gbps" if capacity_mbps >= 1000 else "Mbps"
    traffic_g = traffic_mbps / 1000 if traffic_mbps >= 1000 else traffic_mbps
    traffic_unit = "Gbps" if traffic_mbps >= 1000 else "Mbps"
    return AlarmCopy(
        kind="link_utilization",
        category=meta["category"],
        priority=meta["priority"],
        title=f"【{meta['priority']}·{meta['category']}】骨干链路 {link_name} 利用率越限",
        detail=(
            f"峰值利用率 {util_pct:.1f}% · 阈值 {threshold_pct}% · "
            f"合同带宽 {cap_g:.0f}{cap_unit} · 峰值流量 {traffic_g:.1f}{traffic_unit}"
        ),
        impact=meta["impact"],
        action=meta["action"],
    )


def build_test_notification() -> AlarmCopy:
    meta = _KIND_META["test"]
    return AlarmCopy(
        kind="test",
        category=meta["category"],
        priority=meta["priority"],
        title="【系统自检】Bugis 告警通知渠道联通测试",
        detail="若您收到此消息，说明通知渠道配置正确，可正常投递生产告警。",
        impact=meta["impact"],
        action=meta["action"],
    )


def copy_from_alarm(alarm: Alarm) -> AlarmCopy:
    meta = _KIND_META.get(alarm.kind, {})
    return AlarmCopy(
        kind=alarm.kind,
        category=meta.get("category", "运维告警"),
        priority=meta.get("priority", "—"),
        title=alarm.title,
        detail=alarm.detail or "",
        impact=meta.get("impact", ""),
        action=meta.get("action", "请登录 Bugis 运维平台查看详情。"),
    )


def format_notification_text(alarm: Alarm, *, copy: AlarmCopy | None = None) -> str:
    c = copy or copy_from_alarm(alarm)
    sev = severity_label(alarm.severity.value)
    lines = [
        "━━━━━━━━ Bugis 智能运维告警 ━━━━━━━━",
        f"级别：{sev} ({alarm.severity.value.upper()}) · {c.priority} · {c.category}",
        f"类型：{kind_label(alarm.kind)}",
        "",
        c.title,
        "",
        f"▎详情",
        f"  {c.detail}",
    ]
    if c.impact:
        lines.extend(["", "▎影响评估", f"  {c.impact}"])
    if c.action:
        lines.extend(["", "▎建议处置", f"  {c.action}"])
    if alarm.circuit_id:
        lines.append(f"\n关联专线 ID：{alarm.circuit_id}")
    if alarm.device_id:
        lines.append(f"关联设备 ID：{alarm.device_id}")
    lines.extend(["", "— 本消息由 Bugis SDN 平台自动发送 —"])
    return "\n".join(lines)


def format_notification_payload(alarm: Alarm, *, copy: AlarmCopy | None = None) -> dict[str, Any]:
    c = copy or copy_from_alarm(alarm)
    return {
        "source": "bugis",
        "severity": alarm.severity.value,
        "severity_label": severity_label(alarm.severity.value),
        "priority": c.priority,
        "category": c.category,
        "kind": alarm.kind,
        "kind_label": kind_label(alarm.kind),
        "title": c.title,
        "detail": c.detail,
        "impact": c.impact,
        "action": c.action,
        "circuit_id": alarm.circuit_id,
        "device_id": alarm.device_id,
        "alarm_id": alarm.id,
        "status": alarm.status.value if alarm.status else None,
    }


# Severities auto-acknowledged after a successful outbound notification.
AUTO_ACK_AFTER_NOTIFY: frozenset[AlarmSeverity] = frozenset({
    AlarmSeverity.MINOR,
    AlarmSeverity.WARNING,
    AlarmSeverity.INFO,
})

AUTO_ACK_ACTOR = "system:auto-notify"
