"""Structured JSON logging for production observability.

In development mode, uses human-readable colored output.
In production, emits newline-delimited JSON (NDJSON) for ingestion
by log aggregators (CloudWatch, Datadog, ELK).
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Output format:
        {"ts": "2026-...", "level": "INFO", "logger": "backend.dag", "msg": "...", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Add source location for warnings and above
        if record.levelno >= logging.WARNING:
            entry["file"] = record.pathname
            entry["line"] = record.lineno
            entry["func"] = record.funcName

        # Capture exception info
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Propagate extra fields (e.g., task_id, step_id, duration_ms)
        for key in ("task_id", "step_id", "duration_ms", "cost_usd",
                     "request_id", "user_id", "method", "path", "status_code"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        return json.dumps(entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable colored formatter for local development."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        msg = record.getMessage()
        base = f"{color}{ts} {record.levelname:<8}{self.RESET} {record.name} — {msg}"
        if record.exc_info and record.exc_info[1] is not None:
            base += "\n" + "".join(traceback.format_exception(*record.exc_info))
        return base


def setup_logging(*, is_dev: bool = True, level: str = "INFO") -> None:
    """Configure root logger with structured or dev formatting."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if is_dev:
        handler.setFormatter(DevFormatter())
    else:
        handler.setFormatter(JSONFormatter())

    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for name in ("botocore", "urllib3", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)
