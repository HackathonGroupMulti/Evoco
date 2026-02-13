"""Tests for the circuit breaker pattern."""

import asyncio

import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


@pytest.fixture
def breaker() -> CircuitBreaker:
    """Fresh circuit breaker with low thresholds for fast tests."""
    return CircuitBreaker("test", failure_threshold=3, recovery_timeout=0.2)


@pytest.mark.asyncio
async def test_starts_closed(breaker: CircuitBreaker) -> None:
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_success_keeps_closed(breaker: CircuitBreaker) -> None:
    async with breaker:
        pass  # success
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats["failure_count"] == 0
    assert breaker.stats["success_count"] == 1


@pytest.mark.asyncio
async def test_opens_after_threshold_failures(breaker: CircuitBreaker) -> None:
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_circuit_rejects_immediately(breaker: CircuitBreaker) -> None:
    # Trip the breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    # Now it should reject without running the body
    with pytest.raises(CircuitOpenError) as exc_info:
        async with breaker:
            pass  # should never reach here

    assert "test" in str(exc_info.value)
    assert exc_info.value.breaker_name == "test"


@pytest.mark.asyncio
async def test_transitions_to_half_open_after_timeout(breaker: CircuitBreaker) -> None:
    # Trip the breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.3)

    assert breaker.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit(breaker: CircuitBreaker) -> None:
    # Trip the breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    await asyncio.sleep(0.3)
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful probe
    async with breaker:
        pass

    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens(breaker: CircuitBreaker) -> None:
    # Trip the breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    await asyncio.sleep(0.3)
    assert breaker.state == CircuitState.HALF_OPEN

    # Failed probe
    with pytest.raises(RuntimeError):
        async with breaker:
            raise RuntimeError("still broken")

    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_success_resets_failure_count(breaker: CircuitBreaker) -> None:
    # 2 failures (not enough to trip)
    for _ in range(2):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    assert breaker.state == CircuitState.CLOSED

    # Success resets counter
    async with breaker:
        pass

    assert breaker.stats["failure_count"] == 0

    # 2 more failures should NOT trip (counter was reset)
    for _ in range(2):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_manual_reset(breaker: CircuitBreaker) -> None:
    # Trip it
    for _ in range(3):
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("boom")

    assert breaker.state == CircuitState.OPEN

    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats["failure_count"] == 0


@pytest.mark.asyncio
async def test_stats_output(breaker: CircuitBreaker) -> None:
    stats = breaker.stats
    assert stats["name"] == "test"
    assert stats["state"] == "closed"
    assert stats["failure_threshold"] == 3
    assert stats["recovery_timeout"] == 0.2
