"""Tests for structured logging configuration."""

import json
import logging

from backend.logging_config import DevFormatter, JSONFormatter


def test_json_formatter_outputs_valid_json() -> None:
    """JSONFormatter should produce parseable JSON."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["msg"] == "Hello world"
    assert "ts" in data


def test_json_formatter_includes_source_for_warnings() -> None:
    """Warning+ records should include file/line/func."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="/app/backend/foo.py",
        lineno=99,
        msg="something went wrong",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)

    assert data["file"] == "/app/backend/foo.py"
    assert data["line"] == 99


def test_json_formatter_captures_exception() -> None:
    """Exceptions should be serialized into the JSON output."""
    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)

    assert "exception" in data
    assert data["exception"]["type"] == "ValueError"
    assert data["exception"]["message"] == "test error"


def test_json_formatter_propagates_extra_fields() -> None:
    """Extra fields like task_id should be included."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="step done",
        args=(),
        exc_info=None,
    )
    record.task_id = "abc123"  # type: ignore[attr-defined]
    record.duration_ms = 42.5  # type: ignore[attr-defined]

    output = formatter.format(record)
    data = json.loads(output)

    assert data["task_id"] == "abc123"
    assert data["duration_ms"] == 42.5


def test_dev_formatter_does_not_crash() -> None:
    """DevFormatter should produce a non-empty string."""
    formatter = DevFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert "hello" in output
    assert len(output) > 0
