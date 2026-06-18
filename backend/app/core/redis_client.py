"""Optional Redis cache — degrades gracefully when unavailable or disabled."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("bugis.redis")

_client: Any | None = None
_disabled_logged = False


def redis_enabled() -> bool:
    return bool(get_settings().redis_url.strip())


def get_redis():
    """Return a redis client or None when caching is off / connection fails."""
    global _client, _disabled_logged
    if not redis_enabled():
        return None
    if _client is not None:
        return _client
    try:
        import redis

        _client = redis.Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _client.ping()
        return _client
    except Exception as exc:  # noqa: BLE001
        if not _disabled_logged:
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            _disabled_logged = True
        _client = None
        return None


def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:  # noqa: BLE001
            pass
    _client = None


def cache_get_json(key: str) -> Any | None:
    client = get_redis()
    if not client:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache get failed for %s: %s", key, exc)
        return None


def cache_set_json(key: str, value: Any, ttl_sec: int) -> None:
    client = get_redis()
    if not client or ttl_sec <= 0:
        return
    try:
        client.setex(key, ttl_sec, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache set failed for %s: %s", key, exc)


def cache_delete(*keys: str) -> None:
    client = get_redis()
    if not client or not keys:
        return
    try:
        client.delete(*keys)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache delete failed: %s", exc)


def cache_delete_prefix(prefix: str) -> None:
    client = get_redis()
    if not client or not prefix:
        return
    try:
        for key in client.scan_iter(match=f"{prefix}*", count=200):
            client.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache delete_prefix failed for %s: %s", prefix, exc)
