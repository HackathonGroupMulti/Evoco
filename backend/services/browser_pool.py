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
    """

    def __init__(self, max_browsers: int | None = None) -> None:
        self._max = max_browsers or settings.max_concurrent_browsers
        self._semaphore = asyncio.Semaphore(self._max)
        self._sessions: dict[str, Any] = {}      # domain -> NovaAct instance
        self._locks: dict[str, asyncio.Lock] = {}  # domain -> creation lock
        self._active_count = 0

    @staticmethod
    def _domain_key(url: str) -> str:
        """Extract domain from URL for session keying."""
        if not url.startswith("http"):
            return url
        parsed = urlparse(url)
        return parsed.netloc or url

    async def acquire(self, url: str) -> Any | None:
        """Acquire a browser session for the given URL.

        Blocks if max concurrent browsers are already in use.
        Returns an existing session if one exists for this domain,
        or creates a new one. Returns None if Nova Act isn't configured.
        """
        domain = self._domain_key(url)
        await self._semaphore.acquire()

        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()

        async with self._locks[domain]:
            if domain in self._sessions:
                logger.debug("Reusing browser session for %s", domain)
                return self._sessions[domain]

            session = await self._create_session(url)
            if session is not None:
                self._sessions[domain] = session
                self._active_count += 1
                logger.info(
                    "Created browser session for %s (%d/%d active)",
                    domain, self._active_count, self._max,
                )
            return session

    async def release(self, url: str) -> None:
        """Release a semaphore slot (does NOT close the session)."""
        self._semaphore.release()

    def get_session(self, url: str) -> Any | None:
        """Get an existing session without acquiring a semaphore slot.

        Used by executor.py to check for pooled sessions.
        """
        domain = self._domain_key(url)
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

    async def shutdown(self) -> None:
        """Close all browser sessions. Call this in a finally block."""
        for domain, session in list(self._sessions.items()):
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
