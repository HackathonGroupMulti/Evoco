"""Tests for BrowserPool session lifecycle management."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.browser_pool import BrowserPool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(max_browsers: int = 2, timeout_seconds: int = 60) -> BrowserPool:
    return BrowserPool(max_browsers=max_browsers, timeout_seconds=timeout_seconds)


def _fake_session(domain: str = "example.com") -> MagicMock:
    s = MagicMock()
    s.__exit__ = MagicMock(return_value=None)
    return s


# ---------------------------------------------------------------------------
# Domain key extraction
# ---------------------------------------------------------------------------

class TestDomainKey:
    def test_strips_subdomain_and_path(self) -> None:
        assert BrowserPool._domain_key("https://www.amazon.com/s?k=laptop") == "www.amazon.com"

    def test_non_http_passthrough(self) -> None:
        assert BrowserPool._domain_key("amazon.com") == "amazon.com"

    def test_bare_domain(self) -> None:
        assert BrowserPool._domain_key("https://bestbuy.com") == "bestbuy.com"


# ---------------------------------------------------------------------------
# Session staleness
# ---------------------------------------------------------------------------

class TestStaleness:
    def test_new_session_not_stale(self) -> None:
        pool = _make_pool(timeout_seconds=10)
        pool._last_used["example.com"] = time.monotonic()
        assert not pool._is_stale("example.com")

    def test_old_session_is_stale(self) -> None:
        pool = _make_pool(timeout_seconds=1)
        pool._last_used["example.com"] = time.monotonic() - 5  # 5 s ago
        assert pool._is_stale("example.com")

    def test_unknown_domain_not_stale(self) -> None:
        pool = _make_pool()
        assert not pool._is_stale("unknown.com")

    def test_get_session_returns_none_when_stale(self) -> None:
        pool = _make_pool(timeout_seconds=1)
        pool._sessions["ex.com"] = _fake_session()
        pool._last_used["ex.com"] = time.monotonic() - 5
        assert pool.get_session("https://ex.com") is None

    def test_get_session_returns_session_when_fresh(self) -> None:
        pool = _make_pool(timeout_seconds=60)
        session = _fake_session()
        pool._sessions["ex.com"] = session
        pool._last_used["ex.com"] = time.monotonic()
        assert pool.get_session("https://ex.com") is session


# ---------------------------------------------------------------------------
# Acquire / release
# ---------------------------------------------------------------------------

class TestAcquireRelease:
    @pytest.mark.asyncio
    async def test_acquire_creates_session_when_nova_act_available(self) -> None:
        pool = _make_pool()
        fake = _fake_session()

        with patch.object(pool, "_create_session", new=AsyncMock(return_value=fake)):
            session = await pool.acquire("https://www.amazon.com")

        assert session is fake
        assert pool.active_count == 1
        assert "www.amazon.com" in pool.session_domains

    @pytest.mark.asyncio
    async def test_acquire_reuses_existing_session(self) -> None:
        pool = _make_pool()
        fake = _fake_session()
        pool._sessions["www.amazon.com"] = fake
        pool._last_used["www.amazon.com"] = time.monotonic()

        with patch.object(pool, "_create_session", new=AsyncMock(side_effect=AssertionError("should not create"))):
            session = await pool.acquire("https://www.amazon.com")
            await pool.release("https://www.amazon.com")

        assert session is fake

    @pytest.mark.asyncio
    async def test_acquire_returns_none_when_no_nova_act(self) -> None:
        pool = _make_pool()
        with patch.object(pool, "_create_session", new=AsyncMock(return_value=None)):
            session = await pool.acquire("https://www.amazon.com")
        assert session is None
        assert pool.active_count == 0

    @pytest.mark.asyncio
    async def test_release_updates_last_used(self) -> None:
        pool = _make_pool()
        pool._sessions["ex.com"] = _fake_session()
        pool._semaphore = asyncio.Semaphore(2)
        # Acquire and then release
        await pool._semaphore.acquire()
        pool._last_used["ex.com"] = 0.0  # old timestamp
        await pool.release("https://ex.com")
        assert pool._last_used["ex.com"] > 0.0

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """A pool of size 1 should block a second acquire until first releases."""
        pool = _make_pool(max_browsers=1)
        fake = _fake_session()

        with patch.object(pool, "_create_session", new=AsyncMock(return_value=fake)):
            s1 = await pool.acquire("https://a.com")
            # Second acquire should block — verify it's waiting
            task = asyncio.create_task(pool.acquire("https://b.com"))
            await asyncio.sleep(0.05)
            assert not task.done()
            await pool.release("https://a.com")
            await task


# ---------------------------------------------------------------------------
# Stale eviction
# ---------------------------------------------------------------------------

class TestStaleEviction:
    @pytest.mark.asyncio
    async def test_evicts_stale_session_before_acquire(self) -> None:
        pool = _make_pool(max_browsers=1, timeout_seconds=1)
        stale = _fake_session()
        pool._sessions["stale.com"] = stale
        pool._last_used["stale.com"] = time.monotonic() - 5  # stale
        pool._active_count = 1

        fresh = _fake_session()
        with patch.object(pool, "_create_session", new=AsyncMock(return_value=fresh)):
            session = await pool.acquire("https://fresh.com")

        assert "stale.com" not in pool._sessions
        assert session is fresh


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_clears_all_sessions(self) -> None:
        pool = _make_pool()
        pool._sessions["a.com"] = _fake_session()
        pool._sessions["b.com"] = _fake_session()
        pool._last_used["a.com"] = time.monotonic()
        pool._last_used["b.com"] = time.monotonic()
        pool._active_count = 2

        with patch("asyncio.to_thread", new=AsyncMock()):
            await pool.shutdown()

        assert pool.active_count == 0
        assert pool.session_domains == []
        assert pool._last_used == {}
