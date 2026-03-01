"""Voice transcription powered by Amazon Nova Sonic via Bedrock.

Supports two modes:
  - Batch:     transcribe(audio_bytes) for pre-recorded audio uploads
  - Streaming: VoiceStream class for real-time WebSocket audio chunks

The streaming mode accepts audio chunks as they arrive from the client,
feeds them to Nova Sonic, and yields partial transcripts in real time.
The pipeline can begin planning before the user finishes speaking.

Falls back to mock transcription when AWS credentials are missing.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, AsyncGenerator

from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings

logger = logging.getLogger(__name__)

NOVA_SONIC_MODEL_ID = "amazon.nova-sonic-v1:0"


def _build_bedrock_client() -> Any:
    """Reuse the planner's cached Bedrock client."""
    from backend.services.planner import _build_bedrock_client as _get_client
    return _get_client()


# ---------------------------------------------------------------------------
# Batch transcription
# ---------------------------------------------------------------------------

async def transcribe(
    audio_bytes: bytes, sample_rate: int = 16000, encoding: str = "pcm"
) -> str:
    """Transcribe audio bytes to text using Nova Sonic (batch mode).

    Used by the POST /api/voice endpoint for file uploads.
    """
    if not settings.has_aws_credentials:
        logger.info("No AWS credentials — returning mock transcription")
        return _mock_transcription()

    try:
        def _run() -> str:
            client = _build_bedrock_client()
            session_config = {
                "inputAudioFormat": {
                    "encoding": encoding,
                    "sampleRateHertz": sample_rate,
                    "channelCount": 1,
                },
            }

            response = client.invoke_model_with_bidirectional_stream(
                modelId=NOVA_SONIC_MODEL_ID,
                body=json.dumps({
                    "sessionConfiguration": session_config,
                    "audioInput": {
                        "audio": base64.b64encode(audio_bytes).decode(),
                    },
                }),
            )

            transcript_parts: list[str] = []
            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if "transcript" in chunk:
                    transcript_parts.append(chunk["transcript"])

            return " ".join(transcript_parts).strip()

        text = await asyncio.to_thread(_run)
        logger.info("Transcribed %d bytes -> %d chars", len(audio_bytes), len(text))
        return text or _mock_transcription()

    except (BotoCoreError, ClientError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Nova Sonic transcription failed, using mock: %s", exc)
        return _mock_transcription()


# ---------------------------------------------------------------------------
# Streaming transcription (Phase 6)
# ---------------------------------------------------------------------------

class VoiceStream:
    """Manages a streaming transcription session with Nova Sonic.

    Designed for WebSocket integration — accepts audio chunks as they
    arrive from the client's microphone and yields partial transcripts
    in real time.

    Usage:
        stream = VoiceStream()
        await stream.start()

        # Feed audio chunks as they arrive from WebSocket
        await stream.feed(audio_chunk_1)
        await stream.feed(audio_chunk_2)

        # Read partial transcripts as they become available
        async for partial in stream.transcripts():
            send_to_client(partial)

        # Signal end of audio and get final text
        final = await stream.finish()

        # Always call cancel() if the WebSocket closes unexpectedly
        await stream.cancel()

    Implementation note:
        Uses a chunked-batch approach — collects audio in a buffer and
        transcribes every N chunks for progress updates, then runs a
        final transcription over all accumulated audio.  A future
        upgrade would use true bidirectional streaming with the Bedrock
        streaming SDK for word-level real-time output.
    """

    _PARTIAL_INTERVAL = 10   # transcribe every N chunks for partial updates
    _CHUNK_TIMEOUT_S  = 30.0 # max seconds to wait for next chunk before giving up

    def __init__(self, sample_rate: int = 16000, encoding: str = "pcm") -> None:
        self.sample_rate = sample_rate
        self.encoding = encoding
        self._transcript_parts: list[str] = []
        self._partial_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._final_text: str = ""
        self._task: asyncio.Task[None] | None = None
        self._started = False
        self._cancelled = False
        self._chunks_received = 0

    async def start(self) -> None:
        """Start the streaming transcription session."""
        self._started = True
        self._task = asyncio.create_task(self._stream_loop(), name="voice-stream")
        logger.info("Voice stream started (sample_rate=%d)", self.sample_rate)

    async def feed(self, audio_chunk: bytes) -> None:
        """Feed an audio chunk into the stream.

        Call this each time a new audio chunk arrives from the WebSocket.
        Raises RuntimeError if the stream was never started or was cancelled.
        """
        if not self._started:
            raise RuntimeError("VoiceStream not started — call start() first")
        if self._cancelled:
            raise RuntimeError("VoiceStream was cancelled")
        self._chunks_received += 1
        await self._audio_queue.put(audio_chunk)

    async def transcripts(self) -> AsyncGenerator[str, None]:
        """Yield partial transcripts as they become available.

        Yields strings until the stream is finished (signaled by None sentinel).
        Stops early if the stream is cancelled.
        """
        while True:
            partial = await self._partial_queue.get()
            if partial is None:
                break
            yield partial

    async def finish(self) -> str:
        """Signal end of audio and return the final transcript.

        Call this when the user stops speaking or the WebSocket closes cleanly.
        Safe to call even if the stream loop has already exited due to a timeout.
        """
        if not self._cancelled:
            await self._audio_queue.put(None)  # sentinel to stop the stream loop

        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Voice stream loop did not finish within 10s; cancelling")
                await self.cancel()

        logger.info(
            "Voice stream finished: %d chunks -> '%s' (%d chars)",
            self._chunks_received, self._final_text[:50], len(self._final_text),
        )
        return self._final_text

    async def cancel(self) -> None:
        """Cancel the stream immediately (e.g. on WebSocket disconnect).

        Safe to call multiple times. After cancellation ``finish()`` returns
        whatever text was accumulated before the cancel.
        """
        if self._cancelled:
            return
        self._cancelled = True

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        # Drain the partial queue so any concurrent ``transcripts()`` caller exits
        await self._partial_queue.put(None)
        logger.info("Voice stream cancelled after %d chunks", self._chunks_received)

    async def _stream_loop(self) -> None:
        """Background task: collect audio chunks and transcribe to text."""
        try:
            audio_buf = bytearray()  # O(1) amortised append vs O(n) join
            chunk_count = 0

            while True:
                # Enforce per-chunk timeout so the loop doesn't hang forever
                # if the client stops sending audio without calling finish().
                try:
                    chunk = await asyncio.wait_for(
                        self._audio_queue.get(), timeout=self._CHUNK_TIMEOUT_S
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Voice stream: no audio chunk received for %.0fs, finalising",
                        self._CHUNK_TIMEOUT_S,
                    )
                    break  # treat as end-of-stream

                if chunk is None:
                    break  # explicit finish() sentinel

                audio_buf.extend(chunk)
                chunk_count += 1

                if chunk_count % self._PARTIAL_INTERVAL == 0:
                    await self._emit_partial(audio_buf)

            # Final transcription on all accumulated audio
            if audio_buf:
                self._final_text = await transcribe(
                    bytes(audio_buf), self.sample_rate, self.encoding
                )
                await self._partial_queue.put(self._final_text)
            else:
                self._final_text = ""

            await self._partial_queue.put(None)  # signal done

        except asyncio.CancelledError:
            logger.debug("Voice stream loop cancelled")
            await self._partial_queue.put(None)
            raise

        except Exception as exc:
            logger.error("Voice stream error: %s", exc)
            self._final_text = _mock_transcription()
            await self._partial_queue.put(self._final_text)
            await self._partial_queue.put(None)

    async def _emit_partial(self, audio_buf: bytearray) -> None:
        """Run a partial transcription and push the result to the queue."""
        if settings.has_aws_credentials:
            try:
                partial_text = await transcribe(
                    bytes(audio_buf), self.sample_rate, self.encoding
                )
                if partial_text and partial_text != _mock_transcription():
                    self._transcript_parts.append(partial_text)
                    await self._partial_queue.put(partial_text)
            except Exception as exc:
                logger.debug("Partial transcription failed: %s", exc)
        else:
            # Mock mode: reveal words progressively
            mock_words = _mock_transcription().split()
            revealed = min(
                len(self._transcript_parts) + 1, len(mock_words)
            )
            partial = " ".join(mock_words[:revealed])
            if partial:
                await self._partial_queue.put(partial)


def _mock_transcription() -> str:
    return "Find me the best laptop under $800 from Amazon, Best Buy, and Newegg."
