"""Cursor (keyset) pagination (ADR-0003 §2; context.md §5: lists are always bounded).

A cursor encodes the sort-key position of the last item returned. Repositories fetch
`limit + 1` rows after that position; the extra row only signals that a next page exists.
Cursors are opaque to clients but not secret: they never bypass authorisation, because
every query is still permission- and RLS-filtered.
"""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from relyxus_api.shared.errors.app_errors import ValidationFailedError

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
MAX_CURSOR_LENGTH = 512
CURSOR_FORMAT_VERSION = 1

type CursorPosition = tuple[str | int, ...]

_INVALID_CURSOR_DETAIL = "The cursor is not valid; restart from the first page."


class InvalidCursorError(ValidationFailedError):
    code = "INVALID_CURSOR"


@dataclass(frozen=True, slots=True)
class PageRequest:
    after: CursorPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class Page[ItemT]:
    items: Sequence[ItemT]
    next_cursor: str | None
    limit: int


def encode_cursor(position: CursorPosition) -> str:
    document = json.dumps({"v": CURSOR_FORMAT_VERSION, "p": list(position)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(document.encode()).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str) -> CursorPosition:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        document = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise InvalidCursorError(_INVALID_CURSOR_DETAIL) from error
    if not isinstance(document, dict) or document.get("v") != CURSOR_FORMAT_VERSION:
        raise InvalidCursorError(_INVALID_CURSOR_DETAIL)
    position = document.get("p")
    if not isinstance(position, list) or not all(_is_position_part(part) for part in position):
        raise InvalidCursorError(_INVALID_CURSOR_DETAIL)
    return tuple(position)


def _is_position_part(part: object) -> bool:
    return isinstance(part, str | int) and not isinstance(part, bool)


def build_page[ItemT](
    fetched: Sequence[ItemT], request: PageRequest, get_position: Callable[[ItemT], CursorPosition]
) -> Page[ItemT]:
    """Turn `limit + 1` fetched rows into one page plus the cursor for the next."""
    items = fetched[: request.limit]
    has_more = len(fetched) > request.limit
    next_cursor = encode_cursor(get_position(items[-1])) if has_more and items else None
    return Page(items=items, next_cursor=next_cursor, limit=request.limit)


def get_page_request(
    cursor: Annotated[
        str | None,
        Query(max_length=MAX_CURSOR_LENGTH, description="Opaque cursor from `meta.next_cursor`"),
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_LIMIT, description="Items per page (1-100)")
    ] = DEFAULT_PAGE_LIMIT,
) -> PageRequest:
    return PageRequest(after=decode_cursor(cursor) if cursor else None, limit=limit)


PageRequestDependency = Annotated[PageRequest, Depends(get_page_request)]
