"""DAG-based step executor — runs independent branches in parallel.

Builds a dependency graph from TaskStep.depends_on and uses
asyncio.wait(return_when=FIRST_COMPLETED) to schedule steps
as soon as their dependencies are satisfied.

Algorithm:
  1. Find all steps with no unmet dependencies (ready queue)
  2. Launch ready steps concurrently via asyncio.create_task
  3. Wait for any one to complete (FIRST_COMPLETED)
  4. Update state, check if new steps are now unblocked
  5. Repeat until no steps are running or ready
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from backend.models.task import (
    StepStatus,
    TaskPlan,
    TaskStep,
    WSEvent,
)
from backend.services.executor import execute_step

logger = logging.getLogger(__name__)

EventCallback = Callable[[WSEvent], Coroutine[Any, Any, None]]


class DAGExecutor:
    """Execute a TaskPlan as a DAG with parallel branch support.

    Independent branches (e.g. Amazon vs Best Buy) run concurrently.
    Steps within a branch execute sequentially based on depends_on.
    LLM steps wait for all their browser dependencies before starting.
    """

    def __init__(
        self,
        plan: TaskPlan,
        on_event: EventCallback,
        pool: Any = None,
    ) -> None:
        self.plan = plan
        self.on_event = on_event
        self.pool = pool

        self._steps: dict[str, TaskStep] = {s.id: s for s in plan.steps}
        self._pending: set[str] = {s.id for s in plan.steps}
        self._completed: dict[str, dict[str, Any]] = {}
        self._failed_ids: set[str] = set()

    def _get_ready_steps(self) -> list[TaskStep]:
        """Return steps whose dependencies are all met and not yet started.

        Only scans steps still in the pending set — O(pending) instead of O(all).
        """
        ready: list[TaskStep] = []
        newly_removed: list[str] = []
        for step_id in self._pending:
            step = self._steps[step_id]
            if step.status != StepStatus.PENDING:
                newly_removed.append(step_id)
                continue

            if step.depends_on and self._failed_ids & set(step.depends_on):
                step.status = StepStatus.SKIPPED
                step.error = "dependency failed"
                self._failed_ids.add(step.id)
                newly_removed.append(step_id)
                logger.info(
                    "Skipping step %s (%s) — dependency chain broken",
                    step.id, step.action,
                )
                continue

            deps_met = all(
                dep_id in self._completed for dep_id in step.depends_on
            )
            if deps_met:
                ready.append(step)
                newly_removed.append(step_id)

        self._pending -= set(newly_removed)
        return ready

    def _collect_context_for(self, step: TaskStep) -> list[dict[str, Any]]:
        """Gather results from completed dependencies as context for LLM steps."""
        context: list[dict[str, Any]] = []
        for dep_id in step.depends_on:
            if dep_id in self._completed:
                context.append(self._completed[dep_id])

        # LLM steps with no explicit deps get all completed results
        if not step.depends_on and step.executor.value == "llm":
            context = list(self._completed.values())

        return context

    async def _run_step(self, step: TaskStep) -> tuple[str, dict[str, Any]]:
        """Execute a single step, emitting WS events."""
        step.mark_running()
        await self.on_event(WSEvent(
            task_id=self.plan.task_id,
            event="step_started",
            data={
                "step_id": step.id,
                "action": step.action,
                "description": step.description,
                "group": step.group,
                "executor": step.executor.value,
            },
        ))

        context = self._collect_context_for(step)
        result = await execute_step(step, context=context, pool=self.pool)
        return step.id, result

    async def execute(self) -> dict[str, Any]:
        """Run the full DAG and return an execution summary.

        Returns:
            Dict with completed/failed/skipped counts, results, and IDs.
        """
        task_id = self.plan.task_id
        running: dict[str, asyncio.Task] = {}
        # Reverse lookup: asyncio.Task → step_id (O(1) on exception)
        task_to_step: dict[asyncio.Task, str] = {}

        while True:
            ready = self._get_ready_steps()

            for step in ready:
                logger.info(
                    "DAG: launching step %s (%s) [group=%s]",
                    step.id, step.action, step.group,
                )
                coro = self._run_step(step)
                t = asyncio.create_task(coro)
                running[step.id] = t
                task_to_step[t] = step.id

            if not running:
                break

            done, _ = await asyncio.wait(
                running.values(), return_when=asyncio.FIRST_COMPLETED
            )

            for finished_task in done:
                try:
                    step_id, result = finished_task.result()
                except Exception as exc:
                    step_id = task_to_step.get(finished_task)
                    if step_id is None:
                        continue
                    result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
                    logger.exception(
                        "DAG: step %s raised unhandled exception", step_id,
                    )

                step = self._steps[step_id]
                del running[step_id]
                del task_to_step[finished_task]

                if result.get("success"):
                    step.mark_completed(result)
                    self._completed[step_id] = result
                    logger.info(
                        "DAG: step %s (%s) completed [group=%s]",
                        step_id, step.action, step.group,
                    )
                    await self.on_event(WSEvent(
                        task_id=task_id,
                        event="step_completed",
                        data={"step_id": step_id, "result": result},
                    ))
                else:
                    err_msg = result.get("error", "unknown error")
                    step.mark_failed(err_msg)
                    self._failed_ids.add(step_id)
                    logger.error(
                        "DAG: step %s (%s → %s) FAILED: %s",
                        step_id, step.action, step.target, err_msg,
                    )
                    await self.on_event(WSEvent(
                        task_id=task_id,
                        event="step_failed",
                        data={"step_id": step_id, "error": step.error},
                    ))

        completed_count = len(self._completed)
        failed_count = len(self._failed_ids)
        total = len(self.plan.steps)

        logger.info(
            "DAG execution complete: %d/%d completed, %d failed, %d skipped",
            completed_count, total, failed_count,
            total - completed_count - failed_count,
        )

        return {
            "completed": completed_count,
            "failed": failed_count,
            "skipped": total - completed_count - failed_count,
            "total": total,
            "completed_results": self._completed,
            "failed_ids": list(self._failed_ids),
        }

    @property
    def completed_results(self) -> dict[str, dict[str, Any]]:
        """Results from all successfully completed steps."""
        return self._completed

    @property
    def failed_step_ids(self) -> set[str]:
        """IDs of all failed or skipped steps."""
        return self._failed_ids
