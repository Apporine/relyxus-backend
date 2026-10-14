"""Idempotent replay for mutating requests (ADR-0003 §5, MPS-22A.05)."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.idempotency.model import IdempotencyRecord
from relyxus_api.modules.idempotency.repository import IdempotencyRepository
from relyxus_api.shared.constants import MAX_IDEMPOTENCY_KEY_LENGTH
from relyxus_api.shared.errors.app_errors import ConflictError, ValidationFailedError
from relyxus_api.shared.utils.ids import new_uuid7


class InvalidIdempotencyKeyError(ValidationFailedError):
    code: ClassVar[str] = "INVALID_IDEMPOTENCY_KEY"


class IdempotencyKeyReuseError(ConflictError):
    code: ClassVar[str] = "IDEMPOTENCY_KEY_REUSE"


class IdempotencyInProgressError(ConflictError):
    code: ClassVar[str] = "IDEMPOTENCY_IN_PROGRESS"


@dataclass(frozen=True, slots=True)
class IdempotencyReplay:
    status_code: int
    body: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    record_id: uuid.UUID


def fingerprint_request(method: str, path: str, payload: object) -> str:
    canonical = json.dumps(
        {"method": method.upper(), "path": path, "body": payload},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyService:
    def __init__(self, repository: IdempotencyRepository | None = None) -> None:
        self._repository = repository or IdempotencyRepository()

    async def begin(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        idempotency_key: str,
        method: str,
        path: str,
        payload: object,
    ) -> IdempotencyReservation | IdempotencyReplay:
        key = idempotency_key.strip()
        if not key or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise InvalidIdempotencyKeyError(
                "Idempotency-Key must be 1-128 non-whitespace characters."
            )
        fingerprint = fingerprint_request(method, path, payload)
        existing = await self._repository.find_record(session, organization_id, key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyKeyReuseError(
                    "This Idempotency-Key was already used with a different request body."
                )
            if existing.response_status is None or existing.response_body is None:
                raise IdempotencyInProgressError(
                    "A request with this Idempotency-Key is still being processed."
                )
            return IdempotencyReplay(
                status_code=existing.response_status, body=existing.response_body
            )

        record = IdempotencyRecord(
            id=new_uuid7(),
            organization_id=organization_id,
            idempotency_key=key,
            request_method=method.upper(),
            request_path=path,
            request_fingerprint=fingerprint,
            response_status=None,
            response_body=None,
        )
        try:
            await self._repository.add_record(session, record)
        except IntegrityError as error:
            raise IdempotencyInProgressError(
                "A request with this Idempotency-Key is still being processed."
            ) from error
        return IdempotencyReservation(record_id=record.id)

    async def complete(
        self,
        session: AsyncSession,
        record_id: uuid.UUID,
        *,
        status_code: int,
        body: dict[str, Any],
    ) -> None:
        record = await session.get(IdempotencyRecord, record_id)
        if record is None:
            raise RuntimeError("Idempotency record disappeared before completion")
        record.response_status = status_code
        record.response_body = body
        await session.flush()
