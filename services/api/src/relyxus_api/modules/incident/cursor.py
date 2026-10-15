"""Shared cursor decoding for incident sub-resources ordered by UUIDv7 ID."""

import uuid

from relyxus_api.shared.http.pagination import InvalidCursorError, PageRequest

_INVALID = "The cursor is not valid; restart from the first page."


def decode_id_cursor(page_request: PageRequest) -> uuid.UUID | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], str):
        raise InvalidCursorError(_INVALID)
    try:
        return uuid.UUID(position[0])
    except ValueError as error:
        raise InvalidCursorError(_INVALID) from error
