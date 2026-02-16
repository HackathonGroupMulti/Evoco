"""JWT authentication middleware and dependencies.

Provides:
    - JWT token creation and validation
    - FastAPI dependency for protected routes
    - User model for multi-tenant task isolation
    - Registration and login endpoints

Tokens use HS256 signing with the JWT_SECRET from settings.
When JWT_SECRET is empty, auth is disabled (dev mode).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)

# Optional bearer token extraction (auto_error=False allows unauthenticated access)
_bearer_scheme = HTTPBearer(auto_error=False)


class User(BaseModel):
    """Authenticated user identity."""
    user_id: str
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthRequest(BaseModel):
    """Login/register request body."""
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


# ---------------------------------------------------------------------------
# In-memory user store (swap for DB in production)
# ---------------------------------------------------------------------------

_users: dict[str, dict[str, Any]] = {}  # email -> {password_hash, user_id, ...}


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_token(user_id: str, email: str) -> str:
    """Create a JWT access token."""
    now = time.time()
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now),
        "exp": int(now + settings.jwt_expiry_minutes * 60),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(settings.jwt_secret)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User | None:
    """Extract and validate the current user from JWT.

    Returns None when auth is disabled (no JWT_SECRET configured).
    Raises 401 when auth is enabled but token is missing/invalid.
    """
    if not _auth_enabled():
        return None

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    return User(user_id=payload["sub"], email=payload["email"])


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User | None:
    """Extract user if token is present, otherwise return None."""
    if not _auth_enabled() or credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        return User(user_id=payload["sub"], email=payload["email"])
    except HTTPException:
        return None


async def get_ws_user(websocket: WebSocket) -> User | None:
    """Extract user from WebSocket query parameter (token=...).

    WebSockets can't use Authorization headers, so token is passed as query param.
    """
    if not _auth_enabled():
        return None

    token = websocket.query_params.get("token")
    if not token:
        return None

    try:
        payload = decode_token(token)
        return User(user_id=payload["sub"], email=payload["email"])
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Auth endpoints (register + login)
# ---------------------------------------------------------------------------

def register_user(email: str, password: str) -> tuple[str, str]:
    """Register a new user and return (user_id, token).

    Raises HTTPException if email already exists.
    """
    import uuid

    if email in _users:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = uuid.uuid4().hex[:12]
    _users[email] = {
        "user_id": user_id,
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    token = create_token(user_id, email)
    logger.info("User registered: %s (%s)", email, user_id)
    return user_id, token


def login_user(email: str, password: str) -> tuple[str, str]:
    """Authenticate a user and return (user_id, token).

    Raises HTTPException on invalid credentials.
    """
    user_data = _users.get(email)
    if not user_data or not _verify_password(password, user_data["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = user_data["user_id"]
    token = create_token(user_id, email)
    logger.info("User logged in: %s (%s)", email, user_id)
    return user_id, token
