"""WebSocket endpoint for live task execution updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.task import WSEvent, TaskCommand, OutputFormat
from backend.orchestrator.pipeline import run_task

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Track active WebSocket connections per task."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, task_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(task_id, []).append(ws)

    def disconnect(self, task_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(task_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(task_id, None)

    async def broadcast(self, event: WSEvent) -> None:
        conns = self._connections.get(event.task_id, [])
        payload = event.model_dump_json()
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(event.task_id, ws)


manager = ConnectionManager()


@router.websocket("/api/ws")
async def ws_run_task(ws: WebSocket) -> None:
    """Connect via WebSocket, send a command, and receive live events.

    Protocol:
      1. Client connects to /api/ws
      2. Client sends JSON: {"command": "...", "output_format": "json"}
      3. Server pushes WSEvent JSON messages as the pipeline executes
      4. Server sends final task_done event, then closes
    """
    await ws.accept()
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        command = data.get("command", "")
        output_format = OutputFormat(data.get("output_format", "json"))

        if not command:
            await ws.send_text(json.dumps({"error": "command is required"}))
            await ws.close()
            return

        # Create a temporary task_id placeholder so we can register the WS
        # before the pipeline assigns the real one.  The pipeline's on_event
        # callback will broadcast to whatever task_id each event carries.
        async def _broadcast(event: WSEvent) -> None:
            try:
                await ws.send_text(event.model_dump_json())
            except Exception:
                pass

        result = await run_task(command, output_format, on_event=_broadcast)

        # Send the final result
        await ws.send_text(result.model_dump_json())

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            await ws.send_text(json.dumps({"error": str(exc)}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
