"""Success envelopes shared by every endpoint (ADR-0003 §1-2; context.md §5).

Errors never use these shapes; they are RFC 9457 problem details.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.shared.http.pagination import Page


class SuccessEnvelope[DataT](BaseModel):
    model_config = ConfigDict(frozen=True)

    success: Literal[True] = True
    data: DataT


class ListMeta(BaseModel):
    """No `total`: a count could reveal restricted incidents (MPS-15.07, ADR-0003 §2)."""

    model_config = ConfigDict(frozen=True)

    next_cursor: str | None = Field(examples=["eyJ2IjoxLCJwIjpbIjIwMjYtMTAtMTQiXX0"])
    limit: int = Field(examples=[20])


class ListEnvelope[ItemT](BaseModel):
    model_config = ConfigDict(frozen=True)

    success: Literal[True] = True
    data: list[ItemT]
    meta: ListMeta


def wrap_success[DataT](data: DataT) -> SuccessEnvelope[DataT]:
    return SuccessEnvelope[DataT](data=data)


def wrap_page[ItemT](page: Page[ItemT]) -> ListEnvelope[ItemT]:
    return ListEnvelope[ItemT](
        data=list(page.items), meta=ListMeta(next_cursor=page.next_cursor, limit=page.limit)
    )
