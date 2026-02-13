"""Tests for JWT authentication."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.middleware.auth import _users


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def clear_users():
    """Clear user store between tests."""
    _users.clear()
    yield
    _users.clear()


@pytest.mark.asyncio
async def test_me_without_auth(client: AsyncClient) -> None:
    """Without JWT_SECRET configured, /me should return unauthenticated."""
    resp = await client.get("/api/auth/me")
    data = resp.json()
    assert data["authenticated"] is False


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    """Register a user, then log in with same credentials."""
    # Register
    resp = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    user_id = data["user_id"]

    # Login
    resp = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == user_id
    assert "access_token" in data


@pytest.mark.asyncio
async def test_duplicate_register(client: AsyncClient) -> None:
    """Registering the same email twice should fail."""
    body = {"email": "dupe@example.com", "password": "securepass123"}
    resp = await client.post("/api/auth/register", json=body)
    assert resp.status_code == 200

    resp = await client.post("/api/auth/register", json=body)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    """Login with wrong password should fail."""
    await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "correctpass1"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    """Login with unknown email should fail."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_short_password_rejected(client: AsyncClient) -> None:
    """Passwords under 8 characters should be rejected by validation."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert resp.status_code == 422
