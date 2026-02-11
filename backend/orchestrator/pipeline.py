"""Main orchestration pipeline.

Coordinates the full task lifecycle:
  1. Planning   — decompose command into step DAG via Nova 2 Lite
  2. Execution  — run steps in parallel via DAG executor + browser pool
  3. Degradation — handle partial failures, optionally re-plan
  4. Output     — format results as JSON / CSV / summary
  5. Observability — accumulate costs and build timing trace

Pushes live WSEvent updates through a callback for real-time frontend sync.
"""

from __future__ import annotations

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
from backend.orchestrator.dag import DAGExecutor
from backend.services.browser_pool import BrowserPool
from backend.services.output import format_output
from backend.services.planner import create_plan, replan

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
    """Execute the full pipeline for a command and return the TaskResult.

    Pipeline stages:
      1. Planning   — decompose into step DAG
      2. Execution  — DAG executor with parallel branches
      3. Degradation — branch isolation + adaptive re-planning
      4. Output     — format final result
      5. Trace      — cost aggregation + timing waterfall
    """
    task = store.new_task(command, output_format)
    task_id = task.task_id
    pool = BrowserPool()

    try:
        # ---- Stage 1: Planning ----
        task.status = TaskStatus.PLANNING
        plan_start = datetime.now(timezone.utc)

        await on_event(WSEvent(task_id=task_id, event="planning_started", data={}))

        plan = await create_plan(command, task_id)
        store.set_plan(task_id, plan)

        plan_duration_ms = int(
            (datetime.now(timezone.utc) - plan_start).total_seconds() * 1000
        )

        await on_event(WSEvent(
            task_id=task_id,
            event="plan_ready",
            data={
                "steps": [
                    {
                        "id": s.id,
                        "action": s.action,
                        "target": s.target,
                        "description": s.description,
                        "executor": s.executor.value,
                        "group": s.group,
                        "depends_on": s.depends_on,
                    }
                    for s in plan.steps
                ],
                "planning_ms": plan_duration_ms,
            },
        ))

        # ---- Stage 2: DAG Execution ----
        task.status = TaskStatus.EXECUTING
        exec_start = datetime.now(timezone.utc)

        dag = DAGExecutor(plan=plan, on_event=on_event, pool=pool)
        summary = await dag.execute()

        exec_duration_ms = int(
            (datetime.now(timezone.utc) - exec_start).total_seconds() * 1000
        )

        # ---- Stage 3: Degradation Check ----
        has_completed = summary["completed"] > 0
        all_failed = summary["completed"] == 0 and summary["failed"] > 0

        if all_failed:
            # Adaptive re-planning: ask Nova 2 Lite for alternative approach
            task.status = TaskStatus.REPLANNING
            await on_event(WSEvent(
                task_id=task_id,
                event="replanning",
                data={
                    "reason": "all branches failed",
                    "failed_ids": summary["failed_ids"],
                },
            ))

            failed_info = [
                {
                    "id": s.id,
                    "action": s.action,
                    "target": s.target,
                    "error": s.error,
                }
                for s in plan.steps
                if s.status in (StepStatus.FAILED, StepStatus.SKIPPED)
            ]
            context = list(dag.completed_results.values())

            plan = await replan(command, failed_info, context, task_id)
            store.set_plan(task_id, plan)

            await on_event(WSEvent(
                task_id=task_id,
                event="plan_ready",
                data={
                    "steps": [
                        {
                            "id": s.id,
                            "action": s.action,
                            "target": s.target,
                            "description": s.description,
                            "executor": s.executor.value,
                            "group": s.group,
                            "depends_on": s.depends_on,
                        }
                        for s in plan.steps
                    ],
                    "is_replan": True,
                },
            ))

            # Re-execute with the new plan
            task.status = TaskStatus.EXECUTING
            dag2 = DAGExecutor(plan=plan, on_event=on_event, pool=pool)
            summary = await dag2.execute()
            has_completed = summary["completed"] > 0

        # ---- Stage 4: Determine Final Status ----
        has_failed = summary["failed"] > 0

        if has_completed and not has_failed:
            task.status = TaskStatus.COMPLETED
        elif has_completed and has_failed:
            task.status = TaskStatus.PARTIAL
        else:
            task.status = TaskStatus.FAILED
            task.error = "All steps failed"

        # ---- Stage 5: Output Formatting ----
        output = format_output(plan, output_format)
        task.output = output

        # ---- Stage 6: Cost Aggregation + Timing Trace ----
        total_cost = sum(s.cost_usd for s in plan.steps)
        task.cost_usd = round(total_cost, 6)

        task.finished_at = datetime.now(timezone.utc)
        task.duration_ms = int(
            (task.finished_at - task.created_at).total_seconds() * 1000
        )

        trace = _build_trace(plan, plan_duration_ms, exec_duration_ms)

        await on_event(WSEvent(
            task_id=task_id,
            event="task_done",
            data={
                "status": task.status.value,
                "cost_usd": task.cost_usd,
                "duration_ms": task.duration_ms,
                "steps_completed": summary["completed"],
                "steps_failed": summary["failed"],
                "trace": trace,
            },
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

    finally:
        await pool.shutdown()

    return task


def _build_trace(
    plan: TaskPlan, plan_ms: int, exec_ms: int
) -> dict[str, Any]:
    """Build an observability trace with per-step timing and cost.

    Output format:
        {
            "planning_ms": 1800,
            "execution_ms": 5400,
            "total_cost_usd": 0.0123,
            "steps": [
                {"id": "a1b2", "action": "navigate", "group": "amazon",
                 "executor": "browser", "status": "completed",
                 "duration_ms": 1100, "cost_usd": 0.002, "retries": 0, ...},
                ...
            ]
        }
    """
    steps_trace: list[dict[str, Any]] = []
    for step in plan.steps:
        entry: dict[str, Any] = {
            "id": step.id,
            "action": step.action,
            "group": step.group,
            "executor": step.executor.value,
            "status": step.status.value,
            "cost_usd": step.cost_usd,
            "retries": step.retries,
        }
        if step.started_at and step.finished_at:
            entry["duration_ms"] = int(
                (step.finished_at - step.started_at).total_seconds() * 1000
            )
            entry["started_at"] = step.started_at.isoformat()
            entry["finished_at"] = step.finished_at.isoformat()
        steps_trace.append(entry)

    return {
        "planning_ms": plan_ms,
        "execution_ms": exec_ms,
        "total_cost_usd": round(sum(s.cost_usd for s in plan.steps), 6),
        "steps": steps_trace,
    }
