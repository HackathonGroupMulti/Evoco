"""Prometheus metrics for Evoco.

Exposes a /metrics endpoint (Prometheus text format) and provides
helper counters/histograms for the pipeline and WebSocket layer.

Usage:
    from backend.services.metrics import TASK_COUNTER, STEP_HISTOGRAM
    TASK_COUNTER.labels(status="completed").inc()
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

# Use the default registry so all default process/python metrics are included.

TASK_COUNTER = Counter(
    "evoco_tasks_total",
    "Total number of tasks executed",
    labelnames=["status"],  # completed | partial | failed
)

TASK_CACHE_COUNTER = Counter(
    "evoco_task_cache_total",
    "Result cache hits and misses",
    labelnames=["result"],  # hit | miss
)

STEP_COUNTER = Counter(
    "evoco_steps_total",
    "Total pipeline steps executed",
    labelnames=["executor", "status"],  # browser/llm × completed/failed/skipped
)

STEP_DURATION = Histogram(
    "evoco_step_duration_seconds",
    "Step execution duration",
    labelnames=["executor"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

TASK_DURATION = Histogram(
    "evoco_task_duration_seconds",
    "End-to-end task duration",
    buckets=(1, 5, 10, 30, 60, 120, 300),
)

ACTIVE_TASKS = Gauge(
    "evoco_active_tasks",
    "Number of pipeline tasks currently running",
)

WS_CONNECTIONS = Gauge(
    "evoco_ws_connections",
    "Number of active WebSocket connections",
)

REPLAN_COUNTER = Counter(
    "evoco_replans_total",
    "Number of adaptive re-plans triggered",
    labelnames=["reason"],  # all_failed | majority_failed
)


def metrics_response() -> tuple[bytes, str]:
    """Return (body_bytes, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
