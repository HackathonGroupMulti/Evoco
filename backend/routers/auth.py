"""Authentication endpoints — register, login, and user info."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.config import settings
from backend.middleware.auth import (
    AuthRequest,
    TokenResponse,
    User,
    get_current_user,
    login_user,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(body: AuthRequest) -> TokenResponse:
    """Register a new user account."""
    user_id, token = register_user(body.email, body.password)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expiry_minutes * 60,
        user_id=user_id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: AuthRequest) -> TokenResponse:
    """Authenticate and receive a JWT token."""
    user_id, token = login_user(body.email, body.password)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expiry_minutes * 60,
        user_id=user_id,
    )


@router.get("/me")
async def me(user: User | None = Depends(get_current_user)) -> dict:
    """Get current user info (requires authentication when enabled)."""
    if user is None:
        return {"authenticated": False, "message": "Auth not configured (JWT_SECRET not set)"}
    return {
        "authenticated": True,
        "user_id": user.user_id,
        "email": user.email,
    }
