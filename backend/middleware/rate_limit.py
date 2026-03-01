"""Token-bucket rate limiter middleware.

Implements a per-client token bucket algorithm with configurable
burst capacity and refill rate.

Client identity:
  - Authenticated requests (Bearer JWT present): keyed by ``user:{user_id}``
    so the limit applies per user regardless of IP.
  - Anonymous requests: keyed by IP address (or X-Forwarded-For behind a
    reverse proxy).

Rate limit headers follow the IETF draft standard (RateLimit-*).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.config import settings

logger = logging.getLogger(__name__)


def _user_id_from_bearer(auth_header: str | None) -> str | None:
    """Extract the ``sub`` claim from a Bearer JWT without signature verification.

    Used only to derive a stable rate-limit key — the auth middleware
    still validates the token fully on protected routes.
    Returns None if the header is absent, malformed, or missing ``sub``.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    parts = auth_header[7:].split(".")
    if len(parts) != 3:
        return None
    try:
        # JWT payload is Base64url-encoded; pad to a multiple of 4
        padded = parts[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload.get("sub") or None
    except Exception:
        return None


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Tokens refill at `refill_rate` tokens/second up to `capacity`.
    Each request consumes one token.
    """
    capacity: float
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    @property
    def retry_after(self) -> float:
        """Seconds until the next token is available."""
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client token bucket rate limiter.

    Config (from settings):
        max_tasks_per_minute: steady-state rate (tokens refilled per minute)
        max_concurrent_tasks: burst capacity (max tokens in bucket)

    Exempt paths: /api/health, /api/ws, /api/ws/voice, /api/ws/logs
    """

    # Paths exempt from rate limiting (health checks, WebSockets)
    EXEMPT_PREFIXES = ("/api/health", "/api/auth", "/api/ws", "/docs", "/openapi.json")

    def __init__(self, app, *, cleanup_interval: float = 300.0) -> None:
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.monotonic()

    def _get_client_key(self, request: Request) -> str:
        """Return a stable rate-limit key for this request.

        Authenticated requests use ``user:{user_id}`` so the limit is
        per-user regardless of which IP they connect from.
        Anonymous requests fall back to IP address.
        """
        user_id = _user_id_from_bearer(request.headers.get("authorization"))
        if user_id:
            return f"user:{user_id}"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _get_bucket(self, client_key: str) -> TokenBucket:
        """Get or create a token bucket for a client key."""
        async with self._lock:
            # Periodic cleanup of stale buckets
            now = time.monotonic()
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale(now)
                self._last_cleanup = now

            if client_key not in self._buckets:
                self._buckets[client_key] = TokenBucket(
                    capacity=float(settings.max_concurrent_tasks),
                    refill_rate=settings.max_tasks_per_minute / 60.0,
                )
            return self._buckets[client_key]

    def _cleanup_stale(self, now: float) -> None:
        """Remove buckets that haven't been used in 10 minutes."""
        stale = [
            ip for ip, bucket in self._buckets.items()
            if now - bucket.last_refill > 600.0
        ]
        for ip in stale:
            del self._buckets[ip]
        if stale:
            logger.debug("Cleaned up %d stale rate limit buckets", len(stale))

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for exempt paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return await call_next(request)

        client_ip = self._get_client_key(request)
        bucket = await self._get_bucket(client_ip)

        if not bucket.consume():
            retry_after = round(bucket.retry_after, 1)
            logger.warning(
                "Rate limited %s on %s %s (retry_after=%.1fs)",
                client_ip, request.method, path, retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "RateLimit-Limit": str(settings.max_tasks_per_minute),
                    "RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["RateLimit-Limit"] = str(settings.max_tasks_per_minute)
        response.headers["RateLimit-Remaining"] = str(int(bucket.tokens))
        return response
