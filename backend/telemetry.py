"""OpenTelemetry setup for distributed tracing.

Instruments the FastAPI app and provides helpers for creating
custom spans in the DAG executor, browser pool, and LLM calls.

Traces are exported via OTLP (gRPC) when OTEL_EXPORTER_OTLP_ENDPOINT
is set, otherwise uses a no-op tracer for zero overhead in dev.

Each DAG step gets its own span, linked to the parent task span,
enabling waterfall visualization in Jaeger/Grafana Tempo.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Lazy-initialized tracer
_tracer: Any = None


def _init_tracer() -> Any:
    """Initialize OpenTelemetry with OTLP exporter or no-op fallback."""
    global _tracer

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create({
            "service.name": "evoco-backend",
            "service.version": "0.1.0",
        })

        if endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry: OTLP exporter → %s", endpoint)
        else:
            # No endpoint configured — use SDK provider for local span context
            # but don't export anywhere (zero network overhead)
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry: no-op mode (no OTEL_EXPORTER_OTLP_ENDPOINT)")

        _tracer = trace.get_tracer("evoco")
        return _tracer

    except ImportError:
        logger.info("OpenTelemetry SDK not installed, tracing disabled")
        return _NoopTracer()


class _NoopSpan:
    """No-op span for when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoopTracer:
    """No-op tracer for when OpenTelemetry is not installed."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()


def get_tracer() -> Any:
    """Get the global tracer (lazy-initialized)."""
    global _tracer
    if _tracer is None:
        _tracer = _init_tracer()
    return _tracer


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a traced span with optional attributes.

    Usage:
        with trace_span("dag.step.execute", {"step.id": "a1b2"}) as span:
            result = await do_work()
            span.set_attribute("result.success", True)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI app with automatic request tracing."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry: FastAPI auto-instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed, skipping")
