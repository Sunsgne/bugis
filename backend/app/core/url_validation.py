"""SSRF-safe outbound URL validation for webhooks and controller endpoints."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)

# Cloud metadata endpoints commonly targeted via SSRF.
_BLOCKED_NETS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("100.64.0.0/10"),
)


def is_internal_controller_url(url: str) -> bool:
    """Built-in Bugis controller uses a non-HTTP pseudo scheme."""
    parsed = urlparse(url.strip())
    return parsed.scheme == "internal"


def validate_outbound_http_url(url: str, *, field: str = "url") -> str:
    """Validate http(s) URLs before server-side fetch. Raises ValueError on reject."""
    raw = (url or "").strip()
    if not raw:
        raise ValueError(f"{field} is required")

    if is_internal_controller_url(raw):
        raise ValueError(f"{field} must be an http(s) URL")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{field} must use http or https")
    if parsed.username or parsed.password:
        raise ValueError(f"{field} must not embed credentials")
    if not parsed.hostname:
        raise ValueError(f"{field} must include a hostname")

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError(f"{field} must not target loopback or internal hostnames")

    _assert_ip_allowed(host, field=field)
    return raw


def validate_controller_base_url(url: str) -> str:
    """Controller northbound base URL — allow internal:// for built-in controller."""
    raw = (url or "").strip()
    if is_internal_controller_url(raw):
        return raw
    return validate_outbound_http_url(raw, field="base_url")


def _assert_ip_allowed(host: str, *, field: str) -> None:
    try:
        addr = ipaddress.ip_address(host)
        _reject_ip(addr, field=field)
        return
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # Offline / restricted resolver — static hostname checks already applied.
        return

    if not infos:
        raise ValueError(f"{field} hostname could not be resolved")

    for info in infos:
        ip_str = info[4][0]
        try:
            _reject_ip(ipaddress.ip_address(ip_str), field=field)
        except ValueError:
            raise


def _reject_ip(addr: ipaddress._BaseAddress, *, field: str) -> None:
    for net in _BLOCKED_NETS:
        if addr in net:
            raise ValueError(f"{field} must not target private or link-local addresses")
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        raise ValueError(f"{field} must not target private or link-local addresses")
