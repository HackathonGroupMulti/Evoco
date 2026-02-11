"""Tests for the FastAPI endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "mock"  # no AWS keys in test


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
