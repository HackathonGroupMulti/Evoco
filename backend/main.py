"""Evoco Control Panel — FastAPI entry point."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.logging_config import setup_logging
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.routers import auth, logs, tasks, voice, ws
from backend.services import log_store
from backend.telemetry import instrument_fastapi

setup_logging(
    is_dev=settings.is_dev,
    level="DEBUG" if settings.is_dev else "INFO",
)
log_store.install()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Evoco Control Panel",
    description="Voice & text-controlled autonomous web agent powered by Amazon Nova.",
    version="0.1.0",
)

# Middleware (order matters: outermost runs first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# OpenTelemetry auto-instrumentation
instrument_fastapi(app)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every HTTP request with method, path, status, and duration."""
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method, request.url.path, response.status_code, duration_ms,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


# Routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(voice.router)
app.include_router(ws.router)
app.include_router(logs.router)


@app.get("/api/health")
async def health() -> dict:
    from backend.orchestrator.pipeline import store
    from backend.services.circuit_breaker import bedrock_breaker, nova_act_breaker
    return {
        "status": "ok",
        "aws_configured": settings.has_aws_credentials,
        "nova_act_configured": settings.has_nova_act_key,
        "mode": "live" if settings.has_aws_credentials else "mock",
        "store_backend": store.backend_name,
        "circuit_breakers": {
            "bedrock": bedrock_breaker.stats,
            "nova_act": nova_act_breaker.stats,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_dev,
    )
