"""In-memory ring buffer that captures Python log records for the UI.

Thread-safe: uses deque (thread-safe append) for storage and
loop.call_soon_threadsafe for async queue notifications so logging
from any thread (uvicorn workers, asyncio.to_thread, etc.) works.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Any

MAX_ENTRIES = 500

_entries: deque[dict[str, Any]] = deque(maxlen=MAX_ENTRIES)
_subscribers: list[asyncio.Queue[dict[str, Any]]] = []
_event_loop: asyncio.AbstractEventLoop | None = None


def _format_entry(record: logging.LogRecord) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    # Capture exception traceback so errors show full detail in the UI
    if record.exc_info and record.exc_info[1] is not None:
        entry["traceback"] = "".join(traceback.format_exception(*record.exc_info))
    return entry


class _BroadcastHandler(logging.Handler):
    """Logging handler that stores records and notifies WebSocket subscribers."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = _format_entry(record)
            _entries.append(entry)  # deque.append is thread-safe in CPython
            self._push_to_subscribers(entry)
        except Exception:
            self.handleError(record)

    def _push_to_subscribers(self, entry: dict[str, Any]) -> None:
        """Push entry to all subscriber queues, thread-safe."""
        # Fast path: check if we're on the event loop thread
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for q in list(_subscribers):
            try:
                if loop is not None:
                    q.put_nowait(entry)
                elif _event_loop is not None:
                    _event_loop.call_soon_threadsafe(q.put_nowait, entry)
            except (asyncio.QueueFull, RuntimeError):
                pass


_handler = _BroadcastHandler()


def install() -> None:
    """Attach the broadcast handler to the root logger (call once at startup)."""
    global _event_loop
    try:
        _event_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (e.g. during module import or test collection).
        # The event loop will be captured later when logging happens inside
        # an async context.
        _event_loop = None
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)
    logging.getLogger("evoco").info("Log capture started — backend ready")


def get_recent(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent *limit* log entries."""
    items = list(_entries)
    return items[-limit:]


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    """Create a new subscriber queue for real-time streaming."""
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue[dict[str, Any]]) -> None:
    """Remove a subscriber queue."""
    try:
        _subscribers.remove(q)
    except ValueError:
        pass
