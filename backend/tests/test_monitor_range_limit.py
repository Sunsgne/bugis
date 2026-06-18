"""Sample limit helper for traffic chart windows."""
from __future__ import annotations

# Mirror frontend sampleLimitForWindow logic for regression coverage.
import math


def sample_limit_for_window(span_hours: int) -> int:
    estimated = math.ceil(span_hours * 120 * 1.15)
    return min(max(estimated, 60), 5000)


def test_sample_limit_scales_with_hours():
    assert sample_limit_for_window(1) == 138
    assert sample_limit_for_window(6) == 828
    assert sample_limit_for_window(24) == 3312
    assert sample_limit_for_window(720) == 5000
