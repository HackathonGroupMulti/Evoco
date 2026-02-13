"""Tests for the orchestration pipeline."""

import pytest

from backend.config import settings
from backend.models.task import OutputFormat, TaskStatus, WSEvent
from backend.orchestrator.pipeline import run_task

# Pipeline tests call real AWS/Nova Act in live mode — skip to avoid minutes-long waits
_skip_live = pytest.mark.skipif(
    settings.has_aws_credentials,
    reason="Skipped in live mode — requires real browser automation",
)


@_skip_live
@pytest.mark.asyncio
async def test_full_pipeline_json() -> None:
    """Run the complete pipeline (mock mode) and verify the result."""
    result = await run_task(
        "Find the best laptop under $800 from Amazon and Best Buy",
        OutputFormat.JSON,
    )
    assert result.status == TaskStatus.COMPLETED
    assert result.output is not None
    assert result.output["total_results"] > 0
    assert result.duration_ms is not None and result.duration_ms > 0


@_skip_live
@pytest.mark.asyncio
async def test_full_pipeline_csv() -> None:
    result = await run_task(
        "Find me the best laptop under $800 from Amazon",
        OutputFormat.CSV,
    )
    assert result.status == TaskStatus.COMPLETED
    assert isinstance(result.output, str)
    assert "name,price,rating,source" in result.output


@_skip_live
@pytest.mark.asyncio
async def test_full_pipeline_summary() -> None:
    result = await run_task(
        "Find me the best laptop under $800 from Amazon",
        OutputFormat.SUMMARY,
    )
    assert result.status == TaskStatus.COMPLETED
    assert isinstance(result.output, str)
    assert "Results for:" in result.output


@_skip_live
@pytest.mark.asyncio
async def test_ws_events_are_emitted() -> None:
    """Verify the pipeline emits the expected WebSocket events."""
    events: list[WSEvent] = []

    async def collector(event: WSEvent) -> None:
        events.append(event)

    result = await run_task(
        "Find laptops on Amazon",
        OutputFormat.JSON,
        on_event=collector,
    )
    assert result.status == TaskStatus.COMPLETED

    event_types = [e.event for e in events]
    assert "planning_started" in event_types
    assert "plan_ready" in event_types
    assert "task_done" in event_types
    assert event_types.count("step_started") > 0
    assert event_types.count("step_completed") > 0
