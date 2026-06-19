"""IPv4/IPv6 address validation for device and import schemas."""
from __future__ import annotations

import ipaddress
import re

_IP_FIELD_RE = re.compile(r"^[\d.:a-fA-F]+$")


def validate_ip_address(value: str | None, *, field: str = "ip", required: bool = False) -> str | None:
    """Return normalized IP string or raise ValueError."""
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None

    raw = value.strip()
    if not raw:
        if required:
            raise ValueError(f"{field} is required")
        return None

    if ";" in raw or " " in raw or not _IP_FIELD_RE.match(raw):
        raise ValueError(f"{field} must be a valid IP address")

    try:
        return str(ipaddress.ip_address(raw))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid IP address") from exc
