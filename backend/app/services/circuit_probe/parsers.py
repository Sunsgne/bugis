"""Parse vendor CLI ping output (H3C Comware / Huawei VRP)."""
from __future__ import annotations

import re

_RTT_LINE = re.compile(r"time[=<]\s*([\d.]+)\s*ms", re.I)
_XMIT_RECV = re.compile(
    r"(\d+)\s+packet\(s\)\s+transmitted,\s+(\d+)\s+packet\(s\)\s+received,\s+([\d.]+)%\s+packet\s+loss",
    re.I,
)
_MIN_AVG_MAX = re.compile(
    r"round-trip\s+min/avg/max\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)\s*ms",
    re.I,
)
_H3C_MAC = re.compile(r"([0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4})")


def parse_ping_output(text: str) -> dict:
    """Extract per-reply RTTs and summary loss from ping CLI output."""
    rtts = [float(m.group(1)) for m in _RTT_LINE.finditer(text or "")]
    sent = received = 0
    loss_pct: float | None = None
    avg_ms: float | None = None

    m = _XMIT_RECV.search(text or "")
    if m:
        sent = int(m.group(1))
        received = int(m.group(2))
        loss_pct = float(m.group(3))

    m2 = _MIN_AVG_MAX.search(text or "")
    if m2:
        avg_ms = float(m2.group(2))

    if loss_pct is None and sent:
        loss_pct = round((sent - received) / sent * 100, 3) if sent else 100.0

    if not rtts and avg_ms is not None:
        rtts = [avg_ms]

    return {
        "rtts_ms": rtts,
        "sent": sent or len(rtts),
        "received": received or len(rtts),
        "loss_pct": loss_pct if loss_pct is not None else (0.0 if rtts else 100.0),
        "avg_ms": avg_ms,
    }


def parse_h3c_remote_mac(text: str) -> str | None:
    """Pick first dynamic MAC from `display l2vpn mac-address vsi ...` output."""
    for line in (text or "").splitlines():
        low = line.lower()
        if "mac" not in low and not _H3C_MAC.search(line):
            continue
        m = _H3C_MAC.search(line)
        if m:
            return m.group(1).lower()
    return None
