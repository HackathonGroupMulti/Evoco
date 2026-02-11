"""Main orchestration pipeline.

Coordinates: planner -> step execution -> output formatting.
Pushes live WSEvent updates through a callback.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from backend.models.task import (
    OutputFormat,
    StepStatus,
    TaskPlan,
    TaskResult,
    TaskStatus,
    WSEvent,
)
from backend.services.planner import create_plan
from backend.services.executor import execute_step
from backend.services.output import format_output

logger = logging.getLogger(__name__)

# Type alias for the WS broadcast callback
EventCallback = Callable[[WSEvent], Coroutine[Any, Any, None]]


async def _noop_callback(event: WSEvent) -> None:
    """Default callback that discards events."""


class TaskStore:
    """In-memory task store (swap for Redis/DynamoDB in production)."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskResult] = {}
        self._plans: dict[str, TaskPlan] = {}

    def new_task(self, command: str, output_format: OutputFormat) -> TaskResult:
        task_id = uuid.uuid4().hex[:12]
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            command=command,
            output_format=output_format,
        )
        self._tasks[task_id] = result
        return result

    def get(self, task_id: str) -> TaskResult | None:
        return self._tasks.get(task_id)

    def set_plan(self, task_id: str, plan: TaskPlan) -> None:
        self._plans[task_id] = plan
        if task_id in self._tasks:
            self._tasks[task_id].plan = plan

    def get_plan(self, task_id: str) -> TaskPlan | None:
        return self._plans.get(task_id)

    def list_tasks(self, limit: int = 50) -> list[TaskResult]:
        return sorted(
            self._tasks.values(), key=lambda t: t.created_at, reverse=True
        )[:limit]


# Singleton store
store = TaskStore()


async def run_task(
    command: str,
    output_format: OutputFormat = OutputFormat.JSON,
    on_event: EventCallback = _noop_callback,
) -> TaskResult:
    """Execute the full pipeline for a command and return the TaskResult."""
    task = store.new_task(command, output_format)
    task_id = task.task_id

    try:
        # ---- Planning ----
        task.status = TaskStatus.PLANNING
        await on_event(WSEvent(task_id=task_id, event="planning_started", data={}))

        plan = await create_plan(command, task_id)
        store.set_plan(task_id, plan)

        await on_event(WSEvent(
            task_id=task_id,
            event="plan_ready",
            data={
                "steps": [
                    {"id": s.id, "action": s.action, "target": s.target, "description": s.description}
                    for s in plan.steps
                ]
            },
        ))

        # ---- Execution ----
        task.status = TaskStatus.EXECUTING

        for step in plan.steps:
            # Check that dependencies are met
            deps_ok = all(
                _step_by_id(plan, dep_id) and _step_by_id(plan, dep_id).status == StepStatus.COMPLETED  # type: ignore[union-attr]
                for dep_id in step.depends_on
            )
            if not deps_ok:
                step.mark_failed("dependency not met")
                await on_event(WSEvent(
                    task_id=task_id,
                    event="step_failed",
                    data={"step_id": step.id, "error": "dependency not met"},
                ))
                continue

            step.mark_running()
            await on_event(WSEvent(
                task_id=task_id,
                event="step_started",
                data={"step_id": step.id, "action": step.action, "description": step.description},
            ))

            result = await execute_step(step)

            if result.get("success"):
                step.mark_completed(result)
                await on_event(WSEvent(
                    task_id=task_id,
                    event="step_completed",
                    data={"step_id": step.id, "result": result},
                ))
            else:
                step.mark_failed(result.get("error", "unknown error"))
                await on_event(WSEvent(
                    task_id=task_id,
                    event="step_failed",
                    data={"step_id": step.id, "error": step.error},
                ))

        # ---- Output ----
        output = format_output(plan, output_format)
        task.output = output
        task.status = TaskStatus.COMPLETED
        task.finished_at = datetime.now(timezone.utc)
        task.duration_ms = int(
            (task.finished_at - task.created_at).total_seconds() * 1000
        )

        await on_event(WSEvent(
            task_id=task_id, event="task_done", data={"status": "completed"}
        ))

    except Exception as exc:
        logger.exception("Pipeline failed for task %s", task_id)
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.finished_at = datetime.now(timezone.utc)
        await on_event(WSEvent(
            task_id=task_id,
            event="task_done",
            data={"status": "failed", "error": str(exc)},
        ))

    return task


def _step_by_id(plan: TaskPlan, step_id: str) -> Any:
    for s in plan.steps:
        if s.id == step_id:
            return s
    return None
