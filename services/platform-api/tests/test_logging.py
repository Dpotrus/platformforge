from opentelemetry import trace
from app.observability.logging import configure_logging
from opentelemetry.sdk.trace import TracerProvider
import json
import logging

from app.observability.logging import JsonFormatter


def test_json_formatter_creates_structured_log():
    formatter = JsonFormatter()

    record = logging.LogRecord(
        name="platformforge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Application started",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "platformforge.test"
    assert log_data["message"] == "Application started"
    assert "timestamp" in log_data


def test_json_formatter_includes_exception():
    formatter = JsonFormatter()

    try:
        raise ValueError("Test error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="platformforge.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Operation failed",
        args=(),
        exc_info=exc_info,
    )

    formatted = formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["level"] == "ERROR"
    assert log_data["message"] == "Operation failed"
    assert "ValueError: Test error" in log_data["exception"]

def test_json_formatter_includes_trace_context():
    provider = TracerProvider()
    tracer = provider.get_tracer("platformforge.test")

    formatter = JsonFormatter(service_name="platformforge-api")

    with tracer.start_as_current_span("test-operation") as span:
        record = logging.LogRecord(
            name="platformforge.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Operation completed",
            args=(),
            exc_info=None,
        )

        log_data = json.loads(formatter.format(record))

        span_context = span.get_span_context()

        assert log_data["service"] == "platformforge-api"
        assert log_data["trace_id"] == format(
            span_context.trace_id,
            "032x",
        )
        assert log_data["span_id"] == format(
            span_context.span_id,
            "016x",
        )

    provider.shutdown()


def test_json_formatter_omits_invalid_trace_context():
    formatter = JsonFormatter()

    record = logging.LogRecord(
        name="platformforge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Application starting",
        args=(),
        exc_info=None,
    )

    log_data = json.loads(formatter.format(record))

    assert "trace_id" not in log_data
    assert "span_id" not in log_data

def test_configure_logging_does_not_duplicate_handlers():
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    try:
        configure_logging()
        configure_logging()

        platformforge_handlers = [
            handler
            for handler in root_logger.handlers
            if getattr(handler, "_platformforge_handler", False)
        ]

        assert len(platformforge_handlers) == 1

    finally:
        for handler in root_logger.handlers[:]:
            if getattr(handler, "_platformforge_handler", False):
                root_logger.removeHandler(handler)
                handler.close()

        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)


def test_configure_logging_preserves_existing_handlers():
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    existing_handler = logging.NullHandler()

    try:
        root_logger.addHandler(existing_handler)

        configure_logging()

        assert existing_handler in root_logger.handlers

    finally:
        for handler in root_logger.handlers[:]:
            if getattr(handler, "_platformforge_handler", False):
                root_logger.removeHandler(handler)
                handler.close()

        root_logger.removeHandler(existing_handler)
        existing_handler.close()

        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)