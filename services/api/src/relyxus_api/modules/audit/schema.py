import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.modules.audit.model import ActorType, AuditEvent, AuditOutcome


class AuditEventSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    sequence: int
    occurred_at: datetime
    actor_type: ActorType
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str | None
    outcome: AuditOutcome
    correlation_id: str

    @classmethod
    def from_event(cls, event: AuditEvent) -> "AuditEventSummary":
        return cls(
            id=event.id,
            sequence=event.sequence,
            occurred_at=event.occurred_at,
            actor_type=ActorType(event.actor_type),
            actor_user_id=event.actor_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=AuditOutcome(event.outcome),
            correlation_id=event.correlation_id,
        )


class ChainVerificationFailureView(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    reason: str


class RecordAuditEventRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str = Field(max_length=100)
    target_type: str = Field(max_length=64)
    target_id: str | None = Field(default=None, max_length=128)
    outcome: AuditOutcome
    before_state: dict[str, object] | None = None
    after_state: dict[str, object] | None = None


class ChainVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain_id: uuid.UUID
    is_valid: bool = Field(examples=[True])
    failures: list[ChainVerificationFailureView]
