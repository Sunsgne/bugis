"""Per-link backbone utilization alarm threshold resolution."""
from __future__ import annotations

from typing import Any

from app.models.platform_settings import PlatformSettings


def effective_utilization_threshold(link: Any, platform: PlatformSettings) -> float:
    if getattr(link, "alarm_utilization_pct", None) is not None:
        return float(link.alarm_utilization_pct)
    return float(platform.threshold_link_utilization_pct)


def thresholds_out(link: Any, platform: PlatformSettings) -> dict[str, float | bool]:
    effective = effective_utilization_threshold(link, platform)
    customized = getattr(link, "alarm_utilization_pct", None) is not None
    return {
        "effective_alarm_utilization_pct": effective,
        "alarm_thresholds_customized": customized,
    }
