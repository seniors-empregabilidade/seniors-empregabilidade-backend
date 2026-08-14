import json
import logging
import sys
from datetime import UTC, datetime
from typing import Final

LOG_RECORD_FIELDS: Final = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "exception_type",
)


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        values: list[tuple[str, object]] = [
            ("timestamp", datetime.now(UTC).isoformat(timespec="milliseconds")),
            ("level", record.levelname),
            ("logger", record.name),
            ("event", getattr(record, "event", record.getMessage())),
        ]

        for field in LOG_RECORD_FIELDS[1:]:
            value = getattr(record, field, None)
            if value is not None:
                values.append((field, value))

        return " ".join(
            f"{key}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
            for key, value in values
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
