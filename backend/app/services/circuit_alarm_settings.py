"""Per-circuit SLA alarm threshold resolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.platform_settings import PlatformSettings


@dataclass(frozen=True)
class AlarmThresholds:
    packet_loss_pct: float
    latency_ms: float
    utilization_pct: float
    health_score_min: float


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
