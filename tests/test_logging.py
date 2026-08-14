import logging

from app.core.logging import KeyValueFormatter
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
