"""Tamper-evident audit hash chains (ADR-0003 §6, Q-19)."""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import relyxus_api.models  # noqa: F401
from db_test_support import (
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.modules.audit.model import ActorType, AuditEvent, AuditOutcome
from relyxus_api.modules.audit.repository import AuditRepository
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent, verify_events
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.db.base import Base
from tenancy_fixtures import ORG_A, WORKSPACE_A1

pytestmark = pytest.mark.integration
CORRELATION = "trace-audit-chain-test"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)

    async def seed(session: AsyncSession) -> None:
        session.add(
            Organization(id=ORG_A, name="Alpha", deployment_mode="saas", default_region="eu-west-2")
        )
        await session.flush()
        session.add(
            Workspace(
                id=WORKSPACE_A1,
                organization_id=ORG_A,
                key="alpha",
                name="Alpha",
                data_residency_region="eu-west-2",
            )
        )

    run_as_superuser(url, seed)
    return url


def _event(
    *,
    workspace_id: uuid.UUID | None = WORKSPACE_A1,
    action: str = "incident.declare",
) -> NewAuditEvent:
    return NewAuditEvent(
        organization_id=ORG_A,
        workspace_id=workspace_id,
        actor_type=ActorType.USER,
        actor_user_id=uuid.uuid4(),
        effective_user_id=None,
        action=action,
        target_type="incident",
        target_id=str(uuid.uuid4()),
        outcome=AuditOutcome.SUCCEEDED,
        before_state=None,
        after_state={"status": "triage"},
        correlation_id=CORRELATION,
        occurred_at=datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC),
    )


def test_models_match_migrations(database_url: str) -> None:
    async def diff() -> list[object]:
        engine = create_async_engine(database_url)
        async with engine.connect() as connection:
            differences = await connection.run_sync(
                lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata)
            )
        await engine.dispose()
        return list(differences)

    assert asyncio.run(diff()) == []


def test_workspace_chain_appends_and_verifies(database_url: str) -> None:
    async def append_two_and_verify(session: AsyncSession) -> Sequence[object]:
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        service = AuditService()
        await service.append(session, _event(action="first"))
        await service.append(session, _event(action="second"))
        return await service.verify_chain(session, WORKSPACE_A1)

    assert run_as_probe_role(database_url, append_two_and_verify) == []


def test_organisation_chain_uses_org_id_as_chain_id(database_url: str) -> None:
    async def append_org_event(session: AsyncSession) -> None:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        await AuditService().append(
            session, _event(workspace_id=None, action="org.settings.update")
        )

    run_as_probe_role(database_url, append_org_event)

    async def verify(session: AsyncSession) -> Sequence[object]:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return await AuditService().verify_chain(session, ORG_A)

    assert run_as_probe_role(database_url, verify) == []


def test_cross_tenant_append_is_blocked(database_url: str) -> None:
    other_org = uuid.uuid4()

    async def insert_foreign(session: AsyncSession) -> None:
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        await AuditService().append(
            session,
            NewAuditEvent(
                organization_id=other_org,
                workspace_id=WORKSPACE_A1,
                actor_type=ActorType.USER,
                actor_user_id=uuid.uuid4(),
                effective_user_id=None,
                action="incident.declare",
                target_type="incident",
                target_id=str(uuid.uuid4()),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=None,
                after_state=None,
                correlation_id=CORRELATION,
                occurred_at=datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC),
            ),
        )

    with pytest.raises(DBAPIError, match="row-level security"):
        run_as_probe_role(database_url, insert_foreign)


def test_audit_rows_cannot_be_updated_or_deleted(database_url: str) -> None:
    async def append_one(session: AsyncSession) -> uuid.UUID:
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        record = await AuditService().append(session, _event(action="immutable"))
        return record.id

    event_id = run_as_probe_role(database_url, append_one)

    async def mutate() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError, match="append-only"):
                await connection.execute(
                    text("UPDATE audit_events SET action = 'tampered' WHERE id = :id"),
                    {"id": event_id},
                )
        async with engine.begin() as connection:
            with pytest.raises(DBAPIError, match="append-only"):
                await connection.execute(
                    text("DELETE FROM audit_events WHERE id = :id"), {"id": event_id}
                )
        await engine.dispose()

    asyncio.run(mutate())


def test_verify_detects_tampered_hash_in_memory(database_url: str) -> None:
    async def fetch_events(session: AsyncSession) -> list[AuditEvent]:
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        await AuditService().append(session, _event(action="to-tamper"))
        return await AuditRepository().list_chain_events(session, WORKSPACE_A1)

    events = run_as_probe_role(database_url, fetch_events)
    tampered = events[0]
    tampered.entry_hash = "0" * 64

    reasons = [failure.reason for failure in verify_events(events)]
    assert any("entry_hash" in reason for reason in reasons)
