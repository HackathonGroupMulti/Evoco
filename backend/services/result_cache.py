"""Command result cache with Redis backend and in-memory fallback.

Caches completed TaskResult objects keyed by a SHA-256 hash of the
(command, output_format) pair.  Avoids re-running identical pipelines
within the configured TTL window.

Layout in Redis:
    cache:{sha256_hex}  ->  JSON-serialised TaskResult  (with EX TTL)
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

# Local in-memory store: key -> (expires_at, json_str)
_mem_cache: dict[str, tuple[float, str]] = {}


def _cache_key(command: str, output_format: str) -> str:
    """Return a stable Redis/memory key for the given command + format."""
    digest = hashlib.sha256(f"{command}|{output_format}".encode()).hexdigest()
    return f"cache:{digest}"


def _get_redis():
    """Return a connected redis client or None."""
    if not settings.redis_url:
        return None
    try:
        import redis as redis_lib
        client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def get_cached(command: str, output_format: str) -> Any | None:
    """Return a cached TaskResult (as dict) or None if not found / expired.

    Returns the raw parsed dict so the caller can reconstruct the model.
    """
    ttl = settings.result_cache_ttl_seconds
    if ttl <= 0:
        return None

    key = _cache_key(command, output_format)

    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                import json
                return json.loads(raw)
        except Exception as exc:
            logger.debug("Cache Redis get failed: %s", exc)
    else:
        # In-memory fallback
        entry = _mem_cache.get(key)
        if entry is not None:
            expires_at, json_str = entry
            if time.time() < expires_at:
                import json
                return json.loads(json_str)
            else:
                _mem_cache.pop(key, None)

    return None


def set_cached(command: str, output_format: str, result_json: str) -> None:
    """Store a serialised TaskResult in the cache."""
    ttl = settings.result_cache_ttl_seconds
    if ttl <= 0:
        return

    key = _cache_key(command, output_format)

    r = _get_redis()
    if r is not None:
        try:
            r.set(key, result_json, ex=ttl)
        except Exception as exc:
            logger.debug("Cache Redis set failed: %s", exc)
    else:
        _mem_cache[key] = (time.time() + ttl, result_json)
