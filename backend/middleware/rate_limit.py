"""Token-bucket rate limiter middleware.

Implements a per-client token bucket algorithm with configurable
burst capacity and refill rate. Clients are identified by IP address
(or X-Forwarded-For behind a reverse proxy).

Rate limit headers follow the IETF draft standard (RateLimit-*).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.config import settings

logger = logging.getLogger(__name__)


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

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _get_bucket(self, client_ip: str) -> TokenBucket:
        """Get or create a token bucket for a client."""
        async with self._lock:
            # Periodic cleanup of stale buckets
            now = time.monotonic()
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale(now)
                self._last_cleanup = now

            if client_ip not in self._buckets:
                self._buckets[client_ip] = TokenBucket(
                    capacity=float(settings.max_concurrent_tasks),
                    refill_rate=settings.max_tasks_per_minute / 60.0,
                )
            return self._buckets[client_ip]

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

        client_ip = self._get_client_ip(request)
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
