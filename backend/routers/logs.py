"""Log endpoints — fetch recent logs and stream live via WebSocket."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.log_store import get_recent, subscribe, unsubscribe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])


@router.get("/api/logs")
async def list_logs(limit: int = 200) -> list[dict]:
    """Return the most recent log entries."""
    return get_recent(limit)


@router.websocket("/api/ws/logs")
async def ws_logs(ws: WebSocket) -> None:
    """Stream log entries to the client in real time."""
    await ws.accept()
    q = subscribe()
    try:
        while True:
            entry = await q.get()
            await ws.send_text(json.dumps(entry))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        unsubscribe(q)
        try:
            await ws.close()
        except Exception:
            pass
