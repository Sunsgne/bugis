"""Production security validation and trusted-proxy client IP helpers."""
from __future__ import annotations

import logging
import re

from fastapi import Request

from app.core.config import settings

logger = logging.getLogger("bugis.security")

_WEAK_SECRET_KEY_FRAGMENTS = (
    "change-me",
    "please-change",
    "changeme",
    "secret-in-production",
)
_WEAK_PASSWORDS = frozenset({"admin123", "admin", "password", "change-me-portal-password"})
_WEAK_WEBHOOK_TOKENS = frozenset({"bugis-webhook-token", "test-token", "webhook"})


def _secret_key_weak(key: str) -> bool:
    if len(key) < 32:
        return True
    lower = key.lower()
    return any(frag in lower for frag in _WEAK_SECRET_KEY_FRAGMENTS)


def validate_production_settings() -> None:
    """Refuse to start in production with known-weak defaults."""
    if settings.app_env != "production":
        return
    if getattr(settings, "skip_security_checks", False):
        return

    problems: list[str] = []

    if _secret_key_weak(settings.secret_key):
        problems.append("BUGIS_SECRET_KEY is missing or too weak (need >= 32 random chars)")

    if settings.first_superuser_password in _WEAK_PASSWORDS:
        problems.append("BUGIS_FIRST_SUPERUSER_PASSWORD is a known weak default")

    if settings.webhook_token in _WEAK_WEBHOOK_TOKENS or len(settings.webhook_token) < 16:
        problems.append("BUGIS_WEBHOOK_TOKEN is missing or too weak")

    if "*" in settings.cors_origins:
        problems.append("BUGIS_CORS_ORIGINS must not include '*' in production")

    if settings.dry_run and not settings.telemetry_simulation:
        logger.warning(
            "production is running with BUGIS_DRY_RUN=true (no live device push)"
        )

    if problems:
        raise RuntimeError(
            "Production security checks failed:\n- " + "\n- ".join(problems)
        )


def client_ip_from_request(request: Request) -> str:
    """Resolve client IP, trusting X-Forwarded-For only from configured proxies."""
    if request.client:
        direct = request.client.host
    else:
        direct = "unknown"

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct

    trusted = set(settings.trusted_proxy_ips or [])
    if not trusted:
        return direct

    if direct not in trusted:
        return direct

    return forwarded.split(",")[0].strip() or direct


def metrics_authorized(request: Request) -> bool:
    token = settings.metrics_token
    if not token:
        return False
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        supplied = header[7:].strip()
    else:
        supplied = request.headers.get("x-metrics-token") or ""
    import secrets

    return bool(supplied) and secrets.compare_digest(supplied, token)
