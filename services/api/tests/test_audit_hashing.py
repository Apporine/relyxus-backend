import uuid
from datetime import UTC, datetime

from relyxus_api.modules.audit.hashing import compute_entry_hash, hashed_fields

ORG = uuid.UUID("0192f0c4-0000-7000-8000-000000000001")
WORKSPACE = uuid.UUID("0192f0c4-1111-7000-8000-000000000002")
MOMENT = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)


def test_entry_hash_is_stable_for_the_same_payload() -> None:
    fields = hashed_fields(
        organization_id=ORG,
        workspace_id=WORKSPACE,
        actor_type="user",
        actor_user_id=uuid.UUID("0192f0c4-2222-7000-8000-000000000003"),
        effective_user_id=None,
        action="incident.declare",
        target_type="incident",
        target_id="0192f0c4-3333-7000-8000-000000000004",
        outcome="succeeded",
        before_state=None,
        after_state={"status": "triage"},
        correlation_id="trace-abc-12345",
    )
    first = compute_entry_hash(
        previous_hash=None,
        chain_id=WORKSPACE,
        sequence=1,
        fields=fields,
        occurred_at=MOMENT,
    )
    second = compute_entry_hash(
        previous_hash=None,
        chain_id=WORKSPACE,
        sequence=1,
        fields=fields,
        occurred_at=MOMENT,
    )

    assert first == second
    assert len(first) == 64


def test_changing_previous_hash_changes_entry_hash() -> None:
    fields = hashed_fields(
        organization_id=ORG,
        workspace_id=WORKSPACE,
        actor_type="system",
        actor_user_id=None,
        effective_user_id=None,
        action="workspace.open",
        target_type="workspace",
        target_id=str(WORKSPACE),
        outcome="succeeded",
        before_state=None,
        after_state=None,
        correlation_id="trace-1",
    )
    with_previous = compute_entry_hash(
        previous_hash="a" * 64,
        chain_id=WORKSPACE,
        sequence=2,
        fields=fields,
        occurred_at=MOMENT,
    )
    without_previous = compute_entry_hash(
        previous_hash=None,
        chain_id=WORKSPACE,
        sequence=2,
        fields=fields,
        occurred_at=MOMENT,
    )

    assert with_previous != without_previous
