"""Parse contracted bandwidth from interface descriptions.

Operators annotate backbone ports with tags like ``bw(100Mbps)`` or ``bw(10Gbps)``.
"""
from __future__ import annotations

import re

# bw(100Mbps) · bw(10Gbps) · bw(100M) · bw(10G)
BW_PATTERN = re.compile(
    r"bw\s*\(\s*(\d+(?:\.\d+)?)\s*(Mbps|Gbps|Kbps|M|G|K|Mbit|Gbit|mbps|gbps)?\s*\)",
    re.IGNORECASE,
)


def parse_bw_mbps(text: str | None) -> int | None:
    """Return contracted bandwidth in Mbps from a port description, or None."""
    if not text:
        return None
    match = BW_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "Mbps").upper().replace("BIT", "")
    if unit.startswith("G"):
        return max(1, int(value * 1000))
    if unit.startswith("K"):
        return max(1, int(value / 1000) or 1)
    return max(1, int(value))


def format_bw_tag(mbps: int) -> str:
    """Render a standard bw(...) tag for seeding / documentation."""
    if mbps >= 1000 and mbps % 1000 == 0:
        return f"bw({mbps // 1000}Gbps)"
    return f"bw({mbps}Mbps)"
