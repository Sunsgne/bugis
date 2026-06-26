"""Per-circuit SLA alarm threshold resolution and alarm policy."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.platform_settings import PlatformSettings

CIRCUIT_ALARM_KINDS: tuple[str, ...] = (
    "tunnel_down",
    "circuit_interruption",
    "sla_loss",
    "sla_latency",
    "utilization",
    "health",
    "circuit_flap",
)

DEFAULT_ALARM_SUPPRESS_MINUTES = 60


@dataclass(frozen=True)
class AlarmThresholds:
    packet_loss_pct: float
    latency_ms: float
    utilization_pct: float
    health_score_min: float


def parse_enabled_alarm_kinds(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return list(CIRCUIT_ALARM_KINDS)
    if isinstance(raw, list):
        kinds = [k for k in raw if k in CIRCUIT_ALARM_KINDS]
        return kinds if kinds else list(CIRCUIT_ALARM_KINDS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            kinds = [k for k in parsed if k in CIRCUIT_ALARM_KINDS]
            return kinds if kinds else list(CIRCUIT_ALARM_KINDS)
    except (json.JSONDecodeError, TypeError):
        pass
    return list(CIRCUIT_ALARM_KINDS)


def serialize_enabled_alarm_kinds(kinds: list[str] | None) -> str | None:
    if kinds is None:
        return None
    filtered = [k for k in kinds if k in CIRCUIT_ALARM_KINDS]
    if not filtered or set(filtered) == set(CIRCUIT_ALARM_KINDS):
        return None
    return json.dumps(filtered)


def is_alarm_kind_enabled(circuit: Any, kind: str) -> bool:
    return kind in set(parse_enabled_alarm_kinds(getattr(circuit, "enabled_alarm_kinds", None)))


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def alarm_suppression_until(circuit: Any) -> datetime | None:
    activated = getattr(circuit, "activated_at", None)
    if not activated:
        return None
    minutes = getattr(circuit, "alarm_suppress_minutes", None)
    if minutes is None or minutes <= 0:
        return None
    return _as_utc(activated) + timedelta(minutes=int(minutes))


def alarms_suppressed(circuit: Any) -> bool:
    until = alarm_suppression_until(circuit)
    if until is None:
        return False
    return datetime.now(timezone.utc) < until


def effective_thresholds(circuit: Any, platform: PlatformSettings) -> AlarmThresholds:
    """Return alarm thresholds for a circuit, falling back to platform defaults."""
    return AlarmThresholds(
        packet_loss_pct=(
            circuit.alarm_packet_loss_pct
            if circuit.alarm_packet_loss_pct is not None
            else platform.threshold_packet_loss_pct
        ),
        latency_ms=(
            circuit.alarm_latency_ms
            if circuit.alarm_latency_ms is not None
            else platform.threshold_latency_ms
        ),
        utilization_pct=(
            circuit.alarm_utilization_pct
            if circuit.alarm_utilization_pct is not None
            else platform.threshold_utilization_pct
        ),
        health_score_min=(
            circuit.alarm_health_score_min
            if circuit.alarm_health_score_min is not None
            else platform.threshold_health_score
        ),
    )


def thresholds_out(circuit: Any, platform: PlatformSettings) -> dict[str, float | bool | None]:
    """Serialize effective + override fields for API responses."""
    eff = effective_thresholds(circuit, platform)
    return {
        "alarm_latency_ms": circuit.alarm_latency_ms,
        "alarm_packet_loss_pct": circuit.alarm_packet_loss_pct,
        "alarm_utilization_pct": circuit.alarm_utilization_pct,
        "alarm_health_score_min": circuit.alarm_health_score_min,
        "effective_alarm_latency_ms": eff.latency_ms,
        "effective_alarm_packet_loss_pct": eff.packet_loss_pct,
        "effective_alarm_utilization_pct": eff.utilization_pct,
        "effective_alarm_health_score_min": eff.health_score_min,
        "alarm_thresholds_customized": any(
            v is not None
            for v in (
                circuit.alarm_latency_ms,
                circuit.alarm_packet_loss_pct,
                circuit.alarm_utilization_pct,
                circuit.alarm_health_score_min,
            )
        ),
    }


def alarm_policy_out(circuit: Any) -> dict[str, Any]:
    until = alarm_suppression_until(circuit)
    return {
        "enabled_alarm_kinds": parse_enabled_alarm_kinds(
            getattr(circuit, "enabled_alarm_kinds", None)
        ),
        "alarm_suppress_minutes": getattr(circuit, "alarm_suppress_minutes", None)
        or DEFAULT_ALARM_SUPPRESS_MINUTES,
        "activated_at": getattr(circuit, "activated_at", None),
        "alarms_suppressed": alarms_suppressed(circuit),
        "alarm_suppression_until": until,
    }


def normalize_alarm_policy_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Convert API alarm policy fields for ORM persistence."""
    out = dict(data)
    if "enabled_alarm_kinds" in out:
        out["enabled_alarm_kinds"] = serialize_enabled_alarm_kinds(
            out["enabled_alarm_kinds"]
        )
    return out


def apply_alarm_policy_fields(circuit: Any, data: dict[str, Any]) -> None:
    """Map API alarm policy fields onto a Circuit ORM instance."""
    normalized = normalize_alarm_policy_payload(data)
    if "enabled_alarm_kinds" in normalized:
        circuit.enabled_alarm_kinds = normalized["enabled_alarm_kinds"]
    if "alarm_suppress_minutes" in normalized:
        circuit.alarm_suppress_minutes = normalized["alarm_suppress_minutes"]
