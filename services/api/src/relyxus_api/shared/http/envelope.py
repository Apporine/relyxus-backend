"""Success envelope shared by every endpoint (ADR-0003; context.md §5).

Errors never use this shape; they are RFC 9457 problem details.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SuccessEnvelope[DataT](BaseModel):
    model_config = ConfigDict(frozen=True)

    success: Literal[True] = True
    data: DataT


def wrap_success[DataT](data: DataT) -> SuccessEnvelope[DataT]:
    return SuccessEnvelope[DataT](data=data)
