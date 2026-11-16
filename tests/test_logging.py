import logging

from app.core.logging import KeyValueFormatter, configure_logging
from app.core.middleware import normalize_request_id


def test_key_value_formatter_emits_expected_fields() -> None:
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.__dict__.update(
        {
            "event": "request_completed",
            "request_id": "request-123",
            "method": "GET",
            "path": "/profiles",
            "status_code": 200,
            "duration_ms": 3.5,
        }
    )

    output = KeyValueFormatter().format(record)

    assert 'event="request_completed"' in output
    assert 'request_id="request-123"' in output
    assert 'path="/profiles"' in output
    assert "status_code=200" in output
    assert "duration_ms=3.5" in output


def test_request_id_normalization_preserves_only_safe_values() -> None:
    assert normalize_request_id("safe-request_123.test") == ("safe-request_123.test")
    assert normalize_request_id("unsafe request") != "unsafe request"
    assert normalize_request_id(None)


def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging twice must not stack duplicate app handlers."""
    root_logger = logging.getLogger()
    before = list(root_logger.handlers)

    configure_logging("INFO")
    configure_logging("INFO")

    app_handlers = [
        h for h in root_logger.handlers if getattr(h, "_app_handler", False)
    ]
    assert len(app_handlers) == 1, (
        f"Expected exactly 1 app handler after two calls, got {len(app_handlers)}"
    )

    # Restore previous handlers to avoid polluting other tests.
    root_logger.handlers = before


def test_configure_logging_preserves_foreign_handlers() -> None:
    """Foreign handlers (e.g. pytest caplog) must survive a configure_logging call."""
    root_logger = logging.getLogger()
    before = list(root_logger.handlers)

    foreign = logging.Handler()
    root_logger.addHandler(foreign)

    configure_logging("INFO")

    assert foreign in root_logger.handlers, (
        "configure_logging must not remove handlers it did not install"
    )

    # Restore previous handlers to avoid polluting other tests.
    root_logger.handlers = before
