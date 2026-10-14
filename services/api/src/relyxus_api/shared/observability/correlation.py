"""Per-request correlation ID, visible to every layer and every log line (context.md §12)."""

import re
import uuid
from contextvars import ContextVar

_UNKNOWN = "-"
# Accept a caller's ID only if it is short and harmless; otherwise mint our own, so log
# lines can never be injected through this header.
_ACCEPTED_ID = re.compile(r"[A-Za-z0-9._-]{8,128}")

_current_correlation_id: ContextVar[str] = ContextVar("correlation_id", default=_UNKNOWN)


def get_correlation_id() -> str:
    return _current_correlation_id.get()


def bind_correlation_id(incoming: str | None) -> str:
    correlation_id = (
        incoming if incoming and _ACCEPTED_ID.fullmatch(incoming) else str(uuid.uuid4())
    )
    _current_correlation_id.set(correlation_id)
    return correlation_id
