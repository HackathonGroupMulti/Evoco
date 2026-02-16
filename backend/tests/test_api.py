"""Tests for the FastAPI endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.config import settings
from backend.main import app

# Skip slow integration tests when live credentials are configured
_live_mode = settings.has_aws_credentials
_skip_live = pytest.mark.skipif(
    _live_mode,
    reason="Skipped in live mode — requires real browser automation",
)


@pytest_asyncio.fixture
async def client():
    # Raise rate limits so tests don't hit 429s
    settings.max_tasks_per_minute = 1000
    settings.max_concurrent_tasks = 100

    # Clear any existing rate limiter buckets from prior tests
    layer = app.middleware_stack
    while layer is not None:
        if hasattr(layer, "_buckets"):
            layer._buckets.clear()
            break
        layer = getattr(layer, "app", None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] in ("mock", "live")
    assert "store_backend" in data
    assert "circuit_breakers" in data


@_skip_live
@pytest.mark.asyncio
async def test_create_task_sync(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/tasks/sync",
        json={"command": "Find laptops on Amazon", "output_format": "json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["output"]["total_results"] > 0


@_skip_live
@pytest.mark.asyncio
async def test_create_task_csv(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/tasks/sync",
        json={"command": "Find laptops on Amazon", "output_format": "csv"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "name,price,rating,source" in data["output"]


@_skip_live
@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient) -> None:
    # Create one first
    await client.post(
        "/api/tasks/sync",
        json={"command": "Test task"},
    )
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_empty_command_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/tasks/sync",
        json={"command": ""},
    )
    assert resp.status_code == 422
