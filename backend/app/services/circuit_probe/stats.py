"""RTT / loss / jitter statistics from probe samples."""
from __future__ import annotations

import statistics


def packet_loss_pct(sent: int, received: int) -> float:
    if sent <= 0:
        return 100.0
    return round(max(0.0, (sent - received) / sent * 100), 3)


def jitter_from_rtts(rtts_ms: list[float]) -> float:
    """Mean absolute delta between consecutive RTT samples (RFC 5481 style MDEV-lite)."""
    if len(rtts_ms) < 2:
        return 0.0
    deltas = [abs(rtts_ms[i] - rtts_ms[i - 1]) for i in range(1, len(rtts_ms))]
    return round(sum(deltas) / len(deltas), 2)


def summarize_rtts(rtts_ms: list[float]) -> dict:
    if not rtts_ms:
        return {"min_ms": 0.0, "avg_ms": 0.0, "max_ms": 0.0, "jitter_ms": 0.0}
    return {
        "min_ms": round(min(rtts_ms), 2),
        "avg_ms": round(statistics.mean(rtts_ms), 2),
        "max_ms": round(max(rtts_ms), 2),
        "jitter_ms": jitter_from_rtts(rtts_ms),
    }
