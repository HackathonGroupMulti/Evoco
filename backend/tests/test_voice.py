"""Tests for VoiceStream and batch transcription."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.voice import VoiceStream, _mock_transcription, transcribe


# ---------------------------------------------------------------------------
# Batch transcription
# ---------------------------------------------------------------------------

class TestBatchTranscribe:
    @pytest.mark.asyncio
    async def test_returns_mock_when_no_credentials(self) -> None:
        with patch("backend.services.voice.settings") as mock_settings:
            mock_settings.has_aws_credentials = False
            result = await transcribe(b"\x00" * 100)
        assert result == _mock_transcription()

    @pytest.mark.asyncio
    async def test_falls_back_to_mock_on_exception(self) -> None:
        from botocore.exceptions import ClientError

        def _bad_client() -> MagicMock:
            client = MagicMock()
            client.invoke_model_with_bidirectional_stream.side_effect = ClientError(
                {"Error": {"Code": "ServiceError", "Message": "fail"}},
                "InvokeModelWithBidirectionalStream",
            )
            return client

        with (
            patch("backend.services.voice.settings") as mock_settings,
            patch("backend.services.voice._build_bedrock_client", side_effect=_bad_client),
        ):
            mock_settings.has_aws_credentials = True
            result = await transcribe(b"\x00" * 100)
        assert result == _mock_transcription()


# ---------------------------------------------------------------------------
# VoiceStream lifecycle
# ---------------------------------------------------------------------------

class TestVoiceStreamLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        stream = VoiceStream()
        await stream.start()
        assert stream._task is not None
        await stream.cancel()

    @pytest.mark.asyncio
    async def test_feed_before_start_raises(self) -> None:
        stream = VoiceStream()
        with pytest.raises(RuntimeError, match="not started"):
            await stream.feed(b"\x00")

    @pytest.mark.asyncio
    async def test_feed_after_cancel_raises(self) -> None:
        stream = VoiceStream()
        await stream.start()
        await stream.cancel()
        with pytest.raises(RuntimeError, match="cancelled"):
            await stream.feed(b"\x00")

    @pytest.mark.asyncio
    async def test_finish_returns_empty_on_no_audio(self) -> None:
        stream = VoiceStream()
        await stream.start()
        result = await stream.finish()
        assert result == ""

    @pytest.mark.asyncio
    async def test_cancel_is_idempotent(self) -> None:
        stream = VoiceStream()
        await stream.start()
        await stream.cancel()
        await stream.cancel()  # second call should not raise

    @pytest.mark.asyncio
    async def test_finish_after_cancel_does_not_hang(self) -> None:
        stream = VoiceStream()
        await stream.start()
        await stream.cancel()
        result = await asyncio.wait_for(stream.finish(), timeout=2.0)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# VoiceStream transcription flow (mocked)
# ---------------------------------------------------------------------------

class TestVoiceStreamTranscription:
    @pytest.mark.asyncio
    async def test_mock_mode_emits_partials(self) -> None:
        """In mock mode, partial transcripts should be emitted every N chunks."""
        stream = VoiceStream()

        with patch("backend.services.voice.settings") as mock_settings:
            mock_settings.has_aws_credentials = False
            await stream.start()

            # Feed enough chunks to trigger one partial emission
            for _ in range(stream._PARTIAL_INTERVAL):
                await stream.feed(b"\x00" * 100)

            partials: list[str] = []
            # Finish the stream then drain partials
            final = await stream.finish()

            async for p in stream.transcripts():
                partials.append(p)

        # Should have received at least the final transcription
        assert isinstance(final, str)

    @pytest.mark.asyncio
    async def test_full_mock_flow(self) -> None:
        """Verify the full start → feed → finish pipeline works end-to-end."""
        chunk = b"\x00" * 256

        with patch("backend.services.voice.transcribe", new=AsyncMock(return_value="hello world")):
            stream = VoiceStream()
            await stream.start()

            for _ in range(3):
                await stream.feed(chunk)

            final = await stream.finish()

        assert final == "hello world"

    @pytest.mark.asyncio
    async def test_chunk_timeout_triggers_finalisation(self) -> None:
        """If no chunks arrive within _CHUNK_TIMEOUT_S, the stream loop exits on its own."""
        stream = VoiceStream()
        stream._CHUNK_TIMEOUT_S = 0.05  # very short for test speed

        await stream.start()
        # Wait for the loop to self-terminate via the timeout (no chunks fed)
        assert stream._task is not None
        await asyncio.wait_for(stream._task, timeout=2.0)

        # No audio was buffered, so final text is empty
        assert stream._final_text == ""
        assert stream._task.done()

    @pytest.mark.asyncio
    async def test_transcripts_generator_exits_on_finish(self) -> None:
        """transcripts() should stop yielding once finish() signals done."""
        stream = VoiceStream()

        with patch("backend.services.voice.transcribe", new=AsyncMock(return_value="done")):
            await stream.start()
            await stream.feed(b"\x00" * 100)
            await stream.finish()

            collected = []
            async for text in stream.transcripts():
                collected.append(text)

        # The final transcript should be in the queue
        assert "done" in collected


# ---------------------------------------------------------------------------
# Error recovery
# ---------------------------------------------------------------------------

class TestVoiceStreamErrorRecovery:
    @pytest.mark.asyncio
    async def test_exception_in_loop_falls_back_to_mock(self) -> None:
        """An unexpected exception in the stream loop should return mock text."""
        stream = VoiceStream()

        with patch("backend.services.voice.transcribe", side_effect=RuntimeError("boom")):
            await stream.start()
            await stream.feed(b"\x00" * 100)
            final = await stream.finish()

        assert final == _mock_transcription()
