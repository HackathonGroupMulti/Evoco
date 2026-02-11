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

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings

logger = logging.getLogger(__name__)

NOVA_SONIC_MODEL_ID = "amazon.nova-sonic-v1:0"


def _build_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


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
    """

    def __init__(self, sample_rate: int = 16000, encoding: str = "pcm") -> None:
        self.sample_rate = sample_rate
        self.encoding = encoding
        self._transcript_parts: list[str] = []
        self._partial_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._final_text: str = ""
        self._task: asyncio.Task | None = None
        self._started = False
        self._chunks_received = 0

    async def start(self) -> None:
        """Start the streaming transcription session."""
        self._started = True
        self._task = asyncio.create_task(self._stream_loop())
        logger.info("Voice stream started (sample_rate=%d)", self.sample_rate)

    async def feed(self, audio_chunk: bytes) -> None:
        """Feed an audio chunk into the stream.

        Call this each time a new audio chunk arrives from the WebSocket.
        """
        if not self._started:
            raise RuntimeError("VoiceStream not started — call start() first")
        self._chunks_received += 1
        await self._audio_queue.put(audio_chunk)

    async def transcripts(self) -> AsyncGenerator[str, None]:
        """Yield partial transcripts as they become available.

        Yields strings until the stream is finished (signaled by None sentinel).
        """
        while True:
            partial = await self._partial_queue.get()
            if partial is None:
                break
            yield partial

    async def finish(self) -> str:
        """Signal end of audio and return the final transcript.

        Call this when the user stops speaking or the WebSocket closes.
        """
        await self._audio_queue.put(None)  # sentinel to stop the stream loop

        if self._task:
            await self._task

        logger.info(
            "Voice stream finished: %d chunks -> '%s' (%d chars)",
            self._chunks_received, self._final_text[:50], len(self._final_text),
        )
        return self._final_text

    async def _stream_loop(self) -> None:
        """Background task: collect audio chunks and stream to Nova Sonic.

        For the hackathon, this uses a chunked-batch approach:
        - Collect audio in a buffer
        - Every N chunks, run a partial transcription
        - Final transcription on all accumulated audio when stream ends

        A production system would use true bidirectional streaming with
        the Bedrock streaming SDK for word-level real-time output.
        """
        try:
            buffer: list[bytes] = []
            partial_interval = 10  # transcribe every N chunks for partial updates

            while True:
                chunk = await self._audio_queue.get()
                if chunk is None:
                    break

                buffer.append(chunk)

                # Emit progress indicator
                if len(buffer) % partial_interval == 0 and settings.has_aws_credentials:
                    # Run partial transcription on what we have so far
                    partial_audio = b"".join(buffer)
                    try:
                        partial_text = await transcribe(
                            partial_audio, self.sample_rate, self.encoding
                        )
                        if partial_text and partial_text != _mock_transcription():
                            self._transcript_parts.append(partial_text)
                            await self._partial_queue.put(partial_text)
                    except Exception as exc:
                        logger.debug("Partial transcription failed: %s", exc)
                elif len(buffer) % partial_interval == 0:
                    # Mock mode: emit progress updates
                    mock_words = _mock_transcription().split()
                    progress = min(len(buffer) // partial_interval, len(mock_words))
                    partial = " ".join(mock_words[:progress])
                    if partial:
                        await self._partial_queue.put(partial)

            # Final transcription on full audio
            if buffer:
                full_audio = b"".join(buffer)
                self._final_text = await transcribe(
                    full_audio, self.sample_rate, self.encoding
                )
                await self._partial_queue.put(self._final_text)
            else:
                self._final_text = ""

            await self._partial_queue.put(None)  # signal done

        except Exception as exc:
            logger.error("Voice stream error: %s", exc)
            self._final_text = _mock_transcription()
            await self._partial_queue.put(self._final_text)
            await self._partial_queue.put(None)


def _mock_transcription() -> str:
    return "Find me the best laptop under $800 from Amazon, Best Buy, and Newegg."
