"""WebSocket endpoints for live task execution and voice streaming.

Two WebSocket modes:
  1. Text mode  (/api/ws)       — send JSON command, receive pipeline events
  2. Voice mode (/api/ws/voice) — stream audio chunks, receive partial
                                   transcripts + pipeline events
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.task import OutputFormat, WSEvent
from backend.orchestrator.pipeline import run_task
from backend.services.voice import VoiceStream

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


# ---------------------------------------------------------------------------
# Text mode WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/api/ws")
async def ws_run_task(ws: WebSocket) -> None:
    """Connect via WebSocket, send a command, and receive live events.

    Protocol:
      1. Client connects to /api/ws
      2. Client sends JSON: {"command": "...", "output_format": "json"}
      3. Server pushes WSEvent JSON messages as the pipeline executes
      4. Server sends final task_done event and the full TaskResult, then closes
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


# ---------------------------------------------------------------------------
# Voice mode WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/api/ws/voice")
async def ws_voice_stream(ws: WebSocket) -> None:
    """Stream audio from the client's microphone, transcribe, and execute.

    Protocol:
      1. Client connects to /api/ws/voice
      2. Client sends config JSON: {"sample_rate": 16000, "encoding": "pcm",
                                     "output_format": "json"}
      3. Client streams binary audio frames (raw PCM or encoded)
      4. Server pushes partial transcripts: {"event": "partial_transcript",
                                              "text": "Find me..."}
      5. Client sends JSON: {"event": "audio_end"} when done speaking
      6. Server sends final transcript, then runs the pipeline
      7. Server pushes pipeline WSEvent messages + final TaskResult
      8. Connection closes
    """
    await ws.accept()
    stream: VoiceStream | None = None

    try:
        # Step 1: Receive config
        config_raw = await ws.receive_text()
        config = json.loads(config_raw)
        sample_rate = config.get("sample_rate", 16000)
        encoding = config.get("encoding", "pcm")
        output_format = OutputFormat(config.get("output_format", "json"))

        # Step 2: Start voice stream
        stream = VoiceStream(sample_rate=sample_rate, encoding=encoding)
        await stream.start()

        await ws.send_text(json.dumps({
            "event": "voice_ready",
            "message": "Streaming session started. Send audio frames.",
        }))

        # Step 3: Start reading partial transcripts in background
        transcript_task = asyncio.create_task(
            _forward_transcripts(ws, stream)
        )

        # Step 4: Receive audio chunks until audio_end signal
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.receive":
                if "bytes" in message and message["bytes"]:
                    # Binary frame — audio data
                    await stream.feed(message["bytes"])
                elif "text" in message and message["text"]:
                    data = json.loads(message["text"])
                    if data.get("event") == "audio_end":
                        break
                    # Could also receive base64-encoded audio in text frames
                    if "audio" in data:
                        audio_bytes = base64.b64decode(data["audio"])
                        await stream.feed(audio_bytes)
            else:
                break

        # Step 5: Finalize transcription
        final_text = await stream.finish()
        await transcript_task  # ensure all partials are forwarded

        await ws.send_text(json.dumps({
            "event": "transcript_final",
            "text": final_text,
        }))

        if not final_text.strip():
            await ws.send_text(json.dumps({
                "event": "error",
                "message": "No speech detected",
            }))
            return

        # Step 6: Run the pipeline with the transcribed command
        async def _broadcast(event: WSEvent) -> None:
            try:
                await ws.send_text(event.model_dump_json())
            except Exception:
                pass

        result = await run_task(final_text, output_format, on_event=_broadcast)

        # Send the final result
        await ws.send_text(result.model_dump_json())

    except WebSocketDisconnect:
        logger.info("Voice WebSocket client disconnected")
        if stream and stream._started:
            await stream.finish()
    except Exception as exc:
        logger.exception("Voice WebSocket error")
        try:
            await ws.send_text(json.dumps({"error": str(exc)}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


async def _forward_transcripts(ws: WebSocket, stream: VoiceStream) -> None:
    """Forward partial transcripts from VoiceStream to the WebSocket client."""
    try:
        async for partial in stream.transcripts():
            await ws.send_text(json.dumps({
                "event": "partial_transcript",
                "text": partial,
            }))
    except Exception:
        pass
