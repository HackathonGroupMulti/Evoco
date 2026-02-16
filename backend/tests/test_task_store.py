"""Tests for the task store (in-memory fallback mode)."""

import pytest

from backend.models.task import OutputFormat, TaskStatus
from backend.services.task_store import TaskStore


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> TaskStore:
    """Fresh in-memory store — force memory backend even when Redis is available."""
    monkeypatch.setattr("backend.services.task_store.settings.redis_url", "")
    return TaskStore()


def test_new_task_creates_unique_ids(store: TaskStore) -> None:
    t1 = store.new_task("cmd1", OutputFormat.JSON)
    t2 = store.new_task("cmd2", OutputFormat.JSON)
    assert t1.task_id != t2.task_id


def test_get_returns_created_task(store: TaskStore) -> None:
    t = store.new_task("find laptops", OutputFormat.JSON)
    retrieved = store.get(t.task_id)
    assert retrieved is not None
    assert retrieved.task_id == t.task_id
    assert retrieved.command == "find laptops"


def test_get_returns_none_for_unknown(store: TaskStore) -> None:
    assert store.get("nonexistent") is None


def test_list_tasks_returns_newest_first(store: TaskStore) -> None:
    t1 = store.new_task("first", OutputFormat.JSON)
    store.new_task("second", OutputFormat.JSON)
    t3 = store.new_task("third", OutputFormat.JSON)

    tasks = store.list_tasks(limit=10)
    assert len(tasks) == 3
    assert tasks[0].task_id == t3.task_id
    assert tasks[2].task_id == t1.task_id


def test_list_tasks_respects_limit(store: TaskStore) -> None:
    for i in range(10):
        store.new_task(f"task {i}", OutputFormat.JSON)

    tasks = store.list_tasks(limit=3)
    assert len(tasks) == 3


def test_save_persists_mutations(store: TaskStore) -> None:
    t = store.new_task("test", OutputFormat.JSON)
    t.status = TaskStatus.COMPLETED
    t.output = {"result": "done"}
    store.save(t)

    retrieved = store.get(t.task_id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.output == {"result": "done"}


def test_set_and_get_plan(store: TaskStore) -> None:
    from backend.models.task import TaskPlan, TaskStep

    t = store.new_task("test", OutputFormat.JSON)
    plan = TaskPlan(
        task_id=t.task_id,
        original_command="test",
        steps=[TaskStep(action="navigate", target="https://a.com", description="go")],
    )
    store.set_plan(t.task_id, plan)

    retrieved_plan = store.get_plan(t.task_id)
    assert retrieved_plan is not None
    assert retrieved_plan.task_id == t.task_id
    assert len(retrieved_plan.steps) == 1
    assert retrieved_plan.steps[0].action == "navigate"


def test_backend_name_is_memory(store: TaskStore) -> None:
    """Without Redis, the backend should be 'memory'."""
    assert store.backend_name == "memory"
