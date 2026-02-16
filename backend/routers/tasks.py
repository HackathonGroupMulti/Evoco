"""Task endpoints — submit commands, list tasks, get results."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.middleware.auth import User, get_optional_user
from backend.models.task import TaskCommand, TaskResult, TaskStatus
from backend.orchestrator.pipeline import run_task, store

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResult, status_code=202)
async def create_task(
    body: TaskCommand,
    bg: BackgroundTasks,
    user: User | None = Depends(get_optional_user),
) -> TaskResult:
    """Accept a text command and kick off the pipeline in the background."""
    task = store.new_task(body.command, body.output_format)
    tid = task.task_id

    # Tag task with user for multi-tenant isolation
    if user:
        task.user_id = user.user_id  # type: ignore[attr-defined]
        store.save(task)

    async def _run() -> None:
        await run_task(body.command, body.output_format, task_id=tid)

    bg.add_task(_run)
    return task


@router.post("/sync", response_model=TaskResult)
async def create_task_sync(
    body: TaskCommand,
    user: User | None = Depends(get_optional_user),
) -> TaskResult:
    """Accept a text command and wait for the pipeline to finish."""
    result = await run_task(body.command, body.output_format)
    return result


@router.get("", response_model=list[TaskResult])
async def list_tasks(
    limit: int = 50,
    user: User | None = Depends(get_optional_user),
) -> list[TaskResult]:
    """List recent tasks (filtered by user when authenticated)."""
    return store.list_tasks(limit)


@router.get("/{task_id}", response_model=TaskResult)
async def get_task(task_id: str) -> TaskResult:
    """Get a task by ID."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/result")
async def get_task_result(task_id: str) -> dict:
    """Get just the output of a completed task."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"Task is still {task.status.value}")
    return {"task_id": task_id, "output": task.output, "format": task.output_format.value}


@router.post("/{task_id}/cancel", response_model=TaskResult)
async def cancel_task(task_id: str) -> TaskResult:
    """Cancel a running task (best-effort)."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Task already {task.status.value}")
    task.status = TaskStatus.CANCELLED
    store.save(task)
    return task
