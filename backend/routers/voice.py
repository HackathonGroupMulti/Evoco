"""Voice endpoint — upload audio, transcribe, then run the pipeline."""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile

from backend.models.task import OutputFormat, TaskResult
from backend.orchestrator.pipeline import run_task
from backend.services.voice import transcribe

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("", response_model=TaskResult)
async def voice_command(
    audio: UploadFile = File(...),
    sample_rate: int = Query(16000),
    encoding: str = Query("pcm"),
    output_format: OutputFormat = Query(OutputFormat.JSON),
) -> TaskResult:
    """Accept an audio file, transcribe it, then execute the task pipeline."""
    audio_bytes = await audio.read()
    text = await transcribe(audio_bytes, sample_rate=sample_rate, encoding=encoding)
    result = await run_task(text, output_format)
    return result
