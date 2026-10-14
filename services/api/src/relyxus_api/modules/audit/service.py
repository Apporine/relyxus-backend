"""Append and verify tamper-evident audit chains (ADR-0003 §6, Q-19)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.audit.hashing import compute_entry_hash, hashed_fields
from relyxus_api.modules.audit.model import ActorType, AuditEvent, AuditOutcome
from relyxus_api.modules.audit.repository import AuditRepository
from relyxus_api.shared.errors.app_errors import ValidationFailedError


class InvalidAuditChainError(ValidationFailedError):
    code: ClassVar[str] = "INVALID_AUDIT_CHAIN"


@dataclass(frozen=True, slots=True)
class NewAuditEvent:
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    actor_type: ActorType
    actor_user_id: uuid.UUID | None
    effective_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str | None
    outcome: AuditOutcome
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    correlation_id: str
    occurred_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ChainVerificationFailure:
    sequence: int
    reason: str


def resolve_chain_id(organization_id: uuid.UUID, workspace_id: uuid.UUID | None) -> uuid.UUID:
    return workspace_id if workspace_id is not None else organization_id


def _validate_chain_binding(
    organization_id: uuid.UUID, workspace_id: uuid.UUID | None, chain_id: uuid.UUID
) -> None:
    expected = resolve_chain_id(organization_id, workspace_id)
    if chain_id != expected:
        raise InvalidAuditChainError("chain_id must match the workspace or organisation scope.")


class AuditService:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self._repository = repository or AuditRepository()

    async def append(self, session: AsyncSession, event: NewAuditEvent) -> AuditEvent:
        """Append one event inside the caller's transaction."""
        if not session.in_transaction():
            raise RuntimeError("Audit append must run inside a transaction")
        chain_id = resolve_chain_id(event.organization_id, event.workspace_id)
        _validate_chain_binding(event.organization_id, event.workspace_id, chain_id)

        await self._repository.lock_chain(session, chain_id)
        tail = await self._repository.fetch_chain_tail(session, chain_id)
        sequence = 1 if tail is None else tail.sequence + 1
        previous_hash = None if tail is None else tail.entry_hash
        occurred_at = event.occurred_at or datetime.now(UTC)
        if occurred_at.tzinfo is None:
            raise InvalidAuditChainError("occurred_at must be timezone-aware (UTC).")

        fields = hashed_fields(
            organization_id=event.organization_id,
            workspace_id=event.workspace_id,
            actor_type=event.actor_type.value,
            actor_user_id=event.actor_user_id,
            effective_user_id=event.effective_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=event.outcome.value,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
        )
        entry_hash = compute_entry_hash(
            previous_hash=previous_hash,
            chain_id=chain_id,
            sequence=sequence,
            fields=fields,
            occurred_at=occurred_at,
        )
        record = AuditEvent(
            organization_id=event.organization_id,
            workspace_id=event.workspace_id,
            chain_id=chain_id,
            sequence=sequence,
            occurred_at=occurred_at,
            actor_type=event.actor_type.value,
            actor_user_id=event.actor_user_id,
            effective_user_id=event.effective_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=event.outcome.value,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        return await self._repository.add_event(session, record)

    async def verify_chain(
        self, session: AsyncSession, chain_id: uuid.UUID
    ) -> list[ChainVerificationFailure]:
        events = await self._repository.list_chain_events(session, chain_id)
        return verify_events(events)


def verify_events(events: Sequence[AuditEvent]) -> list[ChainVerificationFailure]:
    failures: list[ChainVerificationFailure] = []
    expected_previous: str | None = None
    expected_sequence = 1
    for event in events:
        if event.sequence != expected_sequence:
            failures.append(
                ChainVerificationFailure(
                    sequence=event.sequence,
                    reason=f"expected sequence {expected_sequence}, got {event.sequence}",
                )
            )
        if event.previous_hash != expected_previous:
            failures.append(
                ChainVerificationFailure(
                    sequence=event.sequence,
                    reason="previous_hash does not link to the prior entry",
                )
            )
        fields = hashed_fields(
            organization_id=event.organization_id,
            workspace_id=event.workspace_id,
            actor_type=event.actor_type,
            actor_user_id=event.actor_user_id,
            effective_user_id=event.effective_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=event.outcome,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
        )
        recomputed = compute_entry_hash(
            previous_hash=event.previous_hash,
            chain_id=event.chain_id,
            sequence=event.sequence,
            fields=fields,
            occurred_at=event.occurred_at,
        )
        if recomputed != event.entry_hash:
            failures.append(
                ChainVerificationFailure(
                    sequence=event.sequence,
                    reason="entry_hash does not match the canonical payload",
                )
            )
        expected_previous = event.entry_hash
        expected_sequence += 1
    return failures
