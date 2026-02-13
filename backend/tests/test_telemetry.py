"""Tests for OpenTelemetry telemetry setup."""

from backend.telemetry import _NoopSpan, _NoopTracer, get_tracer, trace_span


def test_noop_span_does_not_crash() -> None:
    """NoopSpan methods should be callable without error."""
    span = _NoopSpan()
    span.set_attribute("key", "value")
    span.set_status("ok")
    span.record_exception(ValueError("test"))


def test_noop_tracer_returns_noop_span() -> None:
    """NoopTracer should return a usable span."""
    tracer = _NoopTracer()
    span = tracer.start_as_current_span("test")
    assert isinstance(span, _NoopSpan)


def test_trace_span_context_manager() -> None:
    """trace_span should work as a context manager."""
    with trace_span("test.operation", {"key": "value"}) as span:
        # Should not crash, span may be noop or real
        span.set_attribute("result", True)


def test_trace_span_propagates_exception() -> None:
    """Exceptions inside trace_span should propagate."""
    import pytest

    with pytest.raises(ValueError, match="boom"):
        with trace_span("test.failing"):
            raise ValueError("boom")


def test_get_tracer_returns_same_instance() -> None:
    """get_tracer() should return a cached tracer."""
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2
