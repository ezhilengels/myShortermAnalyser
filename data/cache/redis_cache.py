"""
redis_cache.py — Redis caching with in-memory fallback.
If Redis is unavailable, falls back to a simple dict cache.
"""

import json
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── in-memory fallback ──────────────────────────────────────
_memory_cache: dict[str, tuple[Any, float]] = {}


def _get_redis():
    """Return a Redis client or None if unavailable."""
    try:
        import redis as redis_lib
        from config import REDIS_URL
        client = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Store value in Redis (or memory fallback) with TTL in seconds."""
    serialized = json.dumps(value)
    client = _get_redis()
    if client:
        try:
            client.setex(key, ttl, serialized)
            return
        except Exception as e:
            logger.warning(f"Redis set failed ({e}), using memory cache")
    # memory fallback
    _memory_cache[key] = (value, time.time() + ttl)


def cache_get(key: str) -> Optional[Any]:
    """Retrieve value from Redis (or memory fallback). Returns None if expired/missing."""
    client = _get_redis()
    if client:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get failed ({e}), using memory cache")
    # memory fallback
    entry = _memory_cache.get(key)
    if entry:
        value, expires_at = entry
        if time.time() < expires_at:
            return value
        else:
            del _memory_cache[key]
    return None


def cache_delete(key: str) -> None:
    client = _get_redis()
    if client:
        try:
            client.delete(key)
        except Exception:
            pass
    _memory_cache.pop(key, None)
