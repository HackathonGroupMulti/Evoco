"""Persistent task store with Redis backend and in-memory fallback.

Uses Redis as the primary store for multi-instance deployment and
crash recovery. Falls back to in-memory storage when Redis is
unavailable (local dev, CI).

Data layout in Redis:
    task:{task_id}       -> JSON-serialized TaskResult
    plan:{task_id}       -> JSON-serialized TaskPlan
    tasks:timeline       -> sorted set (score=timestamp, member=task_id)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.config import settings
from backend.models.task import OutputFormat, TaskPlan, TaskResult, TaskStatus

logger = logging.getLogger(__name__)

# TTL for task data in Redis (7 days)
_TASK_TTL_SECONDS = 7 * 24 * 60 * 60


class _InMemoryBackend:
    """In-memory fallback when Redis is unavailable."""

    def __init__(self) -> None:
        self._tasks: dict[str, str] = {}
        self._plans: dict[str, str] = {}
        self._timeline: list[tuple[float, str]] = []  # (timestamp, task_id)

    def set_task(self, task_id: str, data: str) -> None:
        self._tasks[task_id] = data

    def get_task(self, task_id: str) -> str | None:
        return self._tasks.get(task_id)

    def set_plan(self, task_id: str, data: str) -> None:
        self._plans[task_id] = data

    def get_plan(self, task_id: str) -> str | None:
        return self._plans.get(task_id)

    def add_to_timeline(self, task_id: str, score: float) -> None:
        self._timeline.append((score, task_id))
        self._timeline.sort(key=lambda x: -x[0])

    def get_timeline(self, limit: int) -> list[str]:
        return [tid for _, tid in self._timeline[:limit]]


class _RedisBackend:
    """Redis-backed persistence layer."""

    def __init__(self, client: Any) -> None:
        self._r = client

    def set_task(self, task_id: str, data: str) -> None:
        self._r.set(f"task:{task_id}", data, ex=_TASK_TTL_SECONDS)

    def get_task(self, task_id: str) -> str | None:
        val = self._r.get(f"task:{task_id}")
        return val.decode() if isinstance(val, bytes) else val

    def set_plan(self, task_id: str, data: str) -> None:
        self._r.set(f"plan:{task_id}", data, ex=_TASK_TTL_SECONDS)

    def get_plan(self, task_id: str) -> str | None:
        val = self._r.get(f"plan:{task_id}")
        return val.decode() if isinstance(val, bytes) else val

    def add_to_timeline(self, task_id: str, score: float) -> None:
        self._r.zadd("tasks:timeline", {task_id: score})

    def get_timeline(self, limit: int) -> list[str]:
        # ZREVRANGE returns newest first
        result = self._r.zrevrange("tasks:timeline", 0, limit - 1)
        return [x.decode() if isinstance(x, bytes) else x for x in result]


def _connect_redis() -> _RedisBackend | None:
    """Try to connect to Redis. Returns None if unavailable."""
    redis_url = settings.redis_url
    if not redis_url:
        return None

    try:
        import redis
        client = redis.from_url(redis_url, decode_responses=False)
        client.ping()
        logger.info("Connected to Redis at %s", redis_url)
        return _RedisBackend(client)
    except Exception as exc:
        logger.warning("Redis unavailable (%s), using in-memory fallback", exc)
        return None


class TaskStore:
    """Unified task store with Redis primary and in-memory fallback.

    All mutations are persisted immediately. Reads are cached in a
    local dict for the lifetime of the process to avoid repeated
    deserialization.
    """

    def __init__(self) -> None:
        backend = _connect_redis()
        if backend is not None:
            self._backend: _RedisBackend | _InMemoryBackend = backend
            self._using_redis = True
        else:
            self._backend = _InMemoryBackend()
            self._using_redis = False

        # Local cache for hot-path reads (avoids repeated JSON deserialize)
        self._cache: dict[str, TaskResult] = {}
        self._plan_cache: dict[str, TaskPlan] = {}

    @property
    def backend_name(self) -> str:
        return "redis" if self._using_redis else "memory"

    def new_task(self, command: str, output_format: OutputFormat) -> TaskResult:
        import uuid
        task_id = uuid.uuid4().hex[:12]
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            command=command,
            output_format=output_format,
        )
        self._persist_task(result)
        self._backend.add_to_timeline(task_id, time.time())
        return result

    def get(self, task_id: str) -> TaskResult | None:
        # Check local cache first
        if task_id in self._cache:
            return self._cache[task_id]

        raw = self._backend.get_task(task_id)
        if raw is None:
            return None

        task = TaskResult.model_validate_json(raw)
        self._cache[task_id] = task
        return task

    def save(self, task: TaskResult) -> None:
        """Persist current task state (call after mutations)."""
        self._persist_task(task)

    def set_plan(self, task_id: str, plan: TaskPlan) -> None:
        self._plan_cache[task_id] = plan
        self._backend.set_plan(task_id, plan.model_dump_json())

        # Also update the task's plan reference
        task = self.get(task_id)
        if task:
            task.plan = plan
            self._persist_task(task)

    def get_plan(self, task_id: str) -> TaskPlan | None:
        if task_id in self._plan_cache:
            return self._plan_cache[task_id]

        raw = self._backend.get_plan(task_id)
        if raw is None:
            return None

        plan = TaskPlan.model_validate_json(raw)
        self._plan_cache[task_id] = plan
        return plan

    def list_tasks(self, limit: int = 50) -> list[TaskResult]:
        """Return most recent tasks, newest first."""
        task_ids = self._backend.get_timeline(limit)
        results: list[TaskResult] = []
        for tid in task_ids:
            task = self.get(tid)
            if task:
                results.append(task)
        return results

    def _persist_task(self, task: TaskResult) -> None:
        """Write task to backend and update local cache."""
        self._cache[task.task_id] = task
        self._backend.set_task(task.task_id, task.model_dump_json())
