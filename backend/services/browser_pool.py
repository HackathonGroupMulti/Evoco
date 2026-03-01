"""Browser session pool — reuses NovaAct sessions per domain.

Manages a bounded number of concurrent browser sessions using
an asyncio semaphore. Sessions are created lazily and reused
for all steps targeting the same site.

Lifecycle:
    pool = BrowserPool(max_browsers=3)
    session = await pool.acquire("https://www.amazon.com")
    # ... use session for navigate, search, extract ...
    await pool.release("https://www.amazon.com")
    # session is NOT closed — reused for next step on same domain
    await pool.shutdown()  # closes everything
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlparse

from backend.config import settings

logger = logging.getLogger(__name__)


class BrowserPool:
    """Bounded pool of NovaAct browser sessions, keyed by domain.

    Concurrency is controlled by an asyncio.Semaphore so at most
    `max_browsers` sessions can be active simultaneously. If a new
    domain is requested when the pool is full, it blocks until a
    slot is released.

    Sessions idle longer than `timeout_seconds` are closed automatically
    before a new session is created, freeing the slot for reuse.
    """

    def __init__(
        self,
        max_browsers: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._max = max_browsers or settings.max_concurrent_browsers
        self._timeout = timeout_seconds if timeout_seconds is not None else settings.browser_timeout_seconds
        self._semaphore = asyncio.Semaphore(self._max)
        self._sessions: dict[str, Any] = {}          # domain -> NovaAct instance
        self._last_used: dict[str, float] = {}        # domain -> epoch timestamp
        self._locks: dict[str, asyncio.Lock] = {}     # domain -> creation lock
        self._active_count = 0

    @staticmethod
    def _domain_key(url: str) -> str:
        """Extract domain from URL for session keying."""
        if not url.startswith("http"):
            return url
        parsed = urlparse(url)
        return parsed.netloc or url

    def _is_stale(self, domain: str) -> bool:
        """Return True if the session for this domain has exceeded the idle timeout."""
        last = self._last_used.get(domain)
        if last is None:
            return False
        return (time.monotonic() - last) > self._timeout

    async def _evict_stale_sessions(self) -> None:
        """Close any sessions that have been idle past the timeout."""
        stale = [d for d in list(self._sessions) if self._is_stale(d)]
        for domain in stale:
            logger.info(
                "Evicting stale browser session for %s (idle > %ds)",
                domain, self._timeout,
            )
            await self._close_session(domain)

    async def acquire(self, url: str) -> Any | None:
        """Acquire a browser session for the given URL.

        Evicts stale sessions first, then blocks if max concurrent browsers
        are already in use. Returns an existing (fresh) session if one
        exists for this domain, or creates a new one. Returns None if
        Nova Act isn't configured. Releases the semaphore automatically
        on failure to prevent leaks.
        """
        domain = self._domain_key(url)

        # Evict idle sessions before blocking on the semaphore so we don't
        # hold up new requests when stale sessions are occupying slots.
        await self._evict_stale_sessions()

        await self._semaphore.acquire()

        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()

        try:
            async with self._locks[domain]:
                if domain in self._sessions:
                    self._last_used[domain] = time.monotonic()
                    logger.debug("Reusing browser session for %s", domain)
                    return self._sessions[domain]

                session = await self._create_session(url)
                if session is not None:
                    self._sessions[domain] = session
                    self._last_used[domain] = time.monotonic()
                    self._active_count += 1
                    logger.info(
                        "Created browser session for %s (%d/%d active)",
                        domain, self._active_count, self._max,
                    )
                    return session

                # Session creation failed — release semaphore to avoid leak
                self._semaphore.release()
                return None
        except Exception:
            self._semaphore.release()
            raise

    async def release(self, url: str) -> None:
        """Release a semaphore slot and update the last-used timestamp."""
        domain = self._domain_key(url)
        self._last_used[domain] = time.monotonic()
        self._semaphore.release()

    def get_session(self, url: str) -> Any | None:
        """Get an existing non-stale session without acquiring a semaphore slot.

        Returns None if the session is stale (caller should re-acquire).
        Used by executor.py to check for pooled sessions.
        """
        domain = self._domain_key(url)
        if self._is_stale(domain):
            return None
        return self._sessions.get(domain)

    async def _create_session(self, url: str) -> Any | None:
        """Create a new NovaAct browser session."""
        if not settings.has_nova_act_key:
            return None

        try:
            from nova_act import NovaAct  # type: ignore[import-untyped]

            starting_page = url if url.startswith("http") else "https://www.google.com"

            def _open() -> Any:
                nova = NovaAct(
                    nova_act_api_key=settings.nova_act_api_key,
                    starting_page=starting_page,
                    headless=settings.headless_browser,
                    tty=False,
                )
                nova.__enter__()
                return nova

            return await asyncio.to_thread(_open)

        except Exception as exc:
            logger.error("Failed to create browser session for %s: %s", url, exc)
            return None

    async def _close_session(self, domain: str) -> None:
        """Close and remove a single session by domain."""
        session = self._sessions.pop(domain, None)
        self._last_used.pop(domain, None)
        if session is None:
            return

        self._active_count = max(0, self._active_count - 1)
        try:
            def _close(s: Any = session) -> None:
                try:
                    s.__exit__(None, None, None)
                except Exception:
                    pass

            await asyncio.to_thread(_close)
            logger.info("Closed browser session for %s", domain)
        except Exception as exc:
            logger.warning("Error closing session for %s: %s", domain, exc)

        # Release the slot so waiting acquires can proceed
        self._semaphore.release()

    async def shutdown(self) -> None:
        """Close all browser sessions. Call this in a finally block."""
        for domain in list(self._sessions.keys()):
            session = self._sessions.get(domain)
            if session is None:
                continue
            try:
                def _close(s: Any = session) -> None:
                    try:
                        s.__exit__(None, None, None)
                    except Exception:
                        pass

                await asyncio.to_thread(_close)
                logger.info("Closed browser session for %s", domain)
            except Exception as exc:
                logger.warning("Error closing session for %s: %s", domain, exc)

        self._sessions.clear()
        self._last_used.clear()
        self._active_count = 0
        logger.info("Browser pool shutdown complete")

    @property
    def active_count(self) -> int:
        """Number of currently open browser sessions."""
        return self._active_count

    @property
    def session_domains(self) -> list[str]:
        """Domains with active sessions."""
        return list(self._sessions.keys())
