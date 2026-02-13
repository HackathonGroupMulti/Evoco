"""Tests for the rate limiting middleware."""

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
async def test_rate_limit_headers_present(client: AsyncClient) -> None:
    """Responses should include RateLimit-* headers."""
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert "RateLimit-Limit" in resp.headers
    assert "RateLimit-Remaining" in resp.headers


@pytest.mark.asyncio
async def test_health_exempt_from_rate_limit(client: AsyncClient) -> None:
    """Health endpoint should NOT have rate limit headers."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    # Health is exempt, so no RateLimit headers
    assert "RateLimit-Limit" not in resp.headers


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    """Every response should include X-Request-ID."""
    resp = await client.get("/api/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 8
