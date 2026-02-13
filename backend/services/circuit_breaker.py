"""Circuit breaker for external service calls (Bedrock, Nova Act).

Implements the three-state circuit breaker pattern:
    CLOSED  → normal operation, requests flow through
    OPEN    → requests fail immediately (fast-fail), avoids hammering a down service
    HALF_OPEN → allow one probe request to test if service recovered

State transitions:
    CLOSED  → OPEN       when failure_count >= failure_threshold
    OPEN    → HALF_OPEN  when recovery_timeout has elapsed
    HALF_OPEN → CLOSED   when probe succeeds
    HALF_OPEN → OPEN     when probe fails

Usage:
    breaker = CircuitBreaker("bedrock", failure_threshold=5, recovery_timeout=30.0)

    async with breaker:
        result = await call_bedrock(...)
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    def __init__(self, breaker_name: str, retry_after: float) -> None:
        self.breaker_name = breaker_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{breaker_name}' is OPEN. "
            f"Retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Async-compatible circuit breaker for protecting external service calls.

    Args:
        name: Human-readable name for logging (e.g., "bedrock", "nova-act").
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait before allowing a probe request.
        half_open_max: Max concurrent requests in half-open state.
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_semaphore = asyncio.Semaphore(half_open_max)
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition OPEN → HALF_OPEN on read)."""
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info(
                "Circuit breaker '%s': OPEN → HALF_OPEN (recovery timeout elapsed)",
                self.name,
            )
        return self._state

    @property
    def stats(self) -> dict[str, Any]:
        """Return circuit breaker statistics for observability."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    async def __aenter__(self) -> CircuitBreaker:
        """Check circuit state before allowing the call."""
        state = self.state

        if state == CircuitState.OPEN:
            retry_after = self.recovery_timeout - (
                time.monotonic() - self._last_failure_time
            )
            raise CircuitOpenError(self.name, max(0.0, retry_after))

        if state == CircuitState.HALF_OPEN:
            # Only allow limited probe requests
            acquired = self._half_open_semaphore._value > 0
            if not acquired:
                raise CircuitOpenError(self.name, 1.0)
            await self._half_open_semaphore.acquire()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Record success or failure and transition state."""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_semaphore.release()

        if exc_type is None:
            await self._on_success()
        else:
            await self._on_failure(exc_val)

        # Don't suppress the exception
        return False

    async def _on_success(self) -> None:
        """Handle a successful call."""
        async with self._lock:
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(
                    "Circuit breaker '%s': HALF_OPEN → CLOSED (probe succeeded)",
                    self.name,
                )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self, exc: BaseException | None) -> None:
        """Handle a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s': HALF_OPEN → OPEN (probe failed: %s)",
                    self.name, exc,
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s': CLOSED → OPEN "
                    "(%d consecutive failures, threshold=%d)",
                    self.name, self._failure_count, self.failure_threshold,
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        logger.info("Circuit breaker '%s': manually reset to CLOSED", self.name)


# Pre-configured circuit breakers for each external service
bedrock_breaker = CircuitBreaker(
    "bedrock", failure_threshold=5, recovery_timeout=30.0,
)
nova_act_breaker = CircuitBreaker(
    "nova-act", failure_threshold=3, recovery_timeout=60.0,
)
