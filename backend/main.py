"""Evoco Control Panel — FastAPI entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers import logs, tasks, voice, ws
from backend.services import log_store

logging.basicConfig(
    level=logging.DEBUG if settings.is_dev else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log_store.install()

app = FastAPI(
    title="Evoco Control Panel",
    description="Voice & text-controlled autonomous web agent powered by Amazon Nova.",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tasks.router)
app.include_router(voice.router)
app.include_router(ws.router)
app.include_router(logs.router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "aws_configured": settings.has_aws_credentials,
        "nova_act_configured": settings.has_nova_act_key,
        "mode": "live" if settings.has_aws_credentials else "mock",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_dev,
    )
