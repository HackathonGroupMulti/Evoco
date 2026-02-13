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
from backend.services.task_store import TaskStore

logger = logging.getLogger(__name__)

# Type alias for the WS broadcast callback
EventCallback = Callable[[WSEvent], Coroutine[Any, Any, None]]


async def _noop_callback(event: WSEvent) -> None:
    """Default callback that discards events."""


# Singleton store (Redis-backed with in-memory fallback)
store = TaskStore()


def _serialize_steps(plan: TaskPlan) -> list[dict[str, Any]]:
    """Serialize plan steps to dicts for WS events (O(n) single pass)."""
    return [
        {
            "id": s.id, "action": s.action, "target": s.target,
            "description": s.description, "executor": s.executor.value,
            "group": s.group, "depends_on": s.depends_on,
        }
        for s in plan.steps
    ]


async def run_task(
    command: str,
    output_format: OutputFormat = OutputFormat.JSON,
    on_event: EventCallback = _noop_callback,
    task_id: str | None = None,
) -> TaskResult:
    """Execute the full pipeline for a command and return the TaskResult.

    Pipeline stages:
      1. Planning   — decompose into step DAG
      2. Execution  — DAG executor with parallel branches
      3. Degradation — branch isolation + adaptive re-planning
      4. Output     — format final result
      5. Trace      — cost aggregation + timing waterfall

    Args:
        task_id: Optional pre-created task ID to reuse (avoids duplicate creation).
    """
    task = store.get(task_id) if task_id else None
    if task is None:
        task = store.new_task(command, output_format)
    task_id = task.task_id
    pool = BrowserPool()

    try:
        # ---- Stage 1: Planning ----
        task.status = TaskStatus.PLANNING
        store.save(task)
        plan_start = datetime.now(timezone.utc)

        await on_event(WSEvent(task_id=task_id, event="planning_started", data={}))

        # Emit a "thinking out loud" reasoning message
        reasoning = _generate_reasoning(command)
        await on_event(WSEvent(
            task_id=task_id,
            event="planning_reasoning",
            data={"text": reasoning},
        ))

        plan = await create_plan(command, task_id)
        store.set_plan(task_id, plan)

        plan_duration_ms = int(
            (datetime.now(timezone.utc) - plan_start).total_seconds() * 1000
        )

        await on_event(WSEvent(
            task_id=task_id,
            event="plan_ready",
            data={"steps": _serialize_steps(plan), "planning_ms": plan_duration_ms},
        ))

        # ---- Stage 2: DAG Execution ----
        task.status = TaskStatus.EXECUTING
        store.save(task)
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
                data={"steps": _serialize_steps(plan), "is_replan": True},
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
        task.finished_at = datetime.now(timezone.utc)
        task.duration_ms = int(
            (task.finished_at - task.created_at).total_seconds() * 1000
        )

        trace = _build_trace(plan, plan_duration_ms, exec_duration_ms)
        task.cost_usd = trace["total_cost_usd"]
        store.save(task)

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
        logger.exception(
            "Pipeline FAILED for task %s — %s: %s", task_id, type(exc).__name__, exc
        )
        task.status = TaskStatus.FAILED
        task.error = f"{type(exc).__name__}: {exc}"
        task.finished_at = datetime.now(timezone.utc)
        store.save(task)
        await on_event(WSEvent(
            task_id=task_id,
            event="task_done",
            data={"status": "failed", "error": task.error},
        ))

    finally:
        await pool.shutdown()

    return task


_SITE_KEYWORDS = ("amazon", "best buy", "newegg", "walmart", "ebay", "yelp", "zillow")
_TOPIC_KEYWORDS = (
    "laptop", "headphone", "monitor", "phone", "tablet", "camera",
    "tv", "speaker", "keyboard", "mouse", "watch", "earbuds",
    "espresso", "coffee", "blender",
)


def _generate_reasoning(command: str) -> str:
    """Generate a human-friendly reasoning message about the planning approach.

    This runs locally (no API call) to provide instant feedback while the
    actual LLM planner works in the background.
    """
    cmd = command.lower()

    # Detect sites mentioned
    sites = [name.title() for name in _SITE_KEYWORDS if name in cmd]

    # Detect product/topic
    topics = [kw + "s" if not kw.endswith("s") else kw for kw in _TOPIC_KEYWORDS if kw in cmd]

    topic_str = topics[0] if topics else "what you're looking for"

    if len(sites) >= 2:
        site_list = " and ".join(sites)
        return (
            f"I'll search {site_list} simultaneously for {topic_str}. "
            f"Each site gets its own browser agent running in parallel, "
            f"then I'll compare everything and rank by value."
        )
    elif len(sites) == 1:
        return (
            f"I'll dispatch a browser agent to {sites[0]} to find {topic_str}. "
            f"I'll extract structured data, then analyze and rank the results."
        )
    else:
        return (
            f"Let me figure out the best approach to research {topic_str}. "
            f"I'll identify the right sites to search, extract data in parallel, "
            f"and synthesize the results into a clear recommendation."
        )


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
    total_cost = 0.0
    for step in plan.steps:
        total_cost += step.cost_usd
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
        "total_cost_usd": round(total_cost, 6),
        "steps": steps_trace,
    }
