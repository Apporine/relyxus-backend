"""Structured JSON logging (context.md §12, MP-28.01).

One JSON object per line, always carrying the request's correlation ID. Callers log
identifiers and outcomes, never secrets, tokens or customer incident content.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar

from relyxus_api.shared.observability.correlation import get_correlation_id

CORRELATION_ATTRIBUTE = "correlation_id"


def install_correlation_record_factory() -> None:
    """Stamp each log record with the correlation ID at creation time, so the ID is right
    even when the line is formatted later or by another handler. Safe to call repeatedly."""
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "is_correlation_factory", False):
        return

    def create_record(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        setattr(record, CORRELATION_ATTRIBUTE, get_correlation_id())
        return record

    create_record.is_correlation_factory = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(create_record)


class JsonLogFormatter(logging.Formatter):
    # Attributes every LogRecord has; anything else was passed via `extra=` and is kept.
    _STANDARD_ATTRIBUTES: ClassVar[frozenset[str]] = frozenset(
        logging.LogRecord("", 0, "", 0, "", None, None).__dict__
    ) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, CORRELATION_ATTRIBUTE, get_correlation_id()),
        }
        entry.update(
            (key, value)
            for key, value in record.__dict__.items()
            if key not in self._STANDARD_ATTRIBUTES
        )
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
