"""Prometheus /metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from backend.services.metrics import metrics_response

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)
