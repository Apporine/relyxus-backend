"""Per-workspace incident numbers (MPS-20.12) and the 0013 backfill."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import (
    build_alembic_config,
    migrate_and_reset,
    require_test_database_url,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    ORG_A,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _declare(client: TestClient, workspace: uuid.UUID) -> int:
    headers = {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }
    response = client.post(
        INCIDENTS, headers=headers, json={"title": "Numbered", "severity": "sev3"}
    )
    assert response.status_code == 201, response.text
    number: int = response.json()["data"]["number"]
    return number


def test_numbers_count_up_independently_per_workspace(client: TestClient) -> None:
    first_b, second_b = _declare(client, WORKSPACE_B1), _declare(client, WORKSPACE_B1)
    first_a = _declare(client, WORKSPACE_A1)

    assert second_b == first_b + 1
    assert first_a == 1


def test_concurrent_declarations_get_distinct_numbers(client: TestClient) -> None:
    with ThreadPoolExecutor(max_workers=6) as pool:
        numbers = list(pool.map(lambda _: _declare(client, WORKSPACE_B1), range(12)))

    assert len(set(numbers)) == 12
    assert sorted(numbers) == list(range(min(numbers), min(numbers) + 12))


def test_backfill_numbers_existing_rows_in_creation_order_and_keeps_rls_forced(
    database_url: str,
) -> None:
    config = build_alembic_config(database_url)
    command.downgrade(config, "0012")
    base = datetime.now(UTC) - timedelta(days=1)
    ids = [uuid.uuid4() for _ in range(3)]

    async def insert_unnumbered(session: AsyncSession) -> None:
        await session.execute(text("DELETE FROM incidents"))
        for offset, incident_id in zip((2, 0, 1), ids, strict=True):
            await session.execute(
                text(
                    "INSERT INTO incidents (id, organization_id, workspace_id, lifecycle_state,"
                    " severity, title, created_at, updated_at)"
                    " VALUES (:id, :org, :ws, 'triage', 'sev3', 'old', :created, :created)"
                ),
                {
                    "id": incident_id,
                    "org": ORG_A,
                    "ws": WORKSPACE_A1,
                    "created": base + timedelta(minutes=offset),
                },
            )

    run_as_superuser(database_url, insert_unnumbered)
    command.upgrade(config, "head")

    async def read(session: AsyncSession) -> tuple[dict[uuid.UUID, int], bool]:
        rows = await session.execute(text("SELECT id, number FROM incidents"))
        forced = await session.scalar(
            text("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'incidents'")
        )
        return {row[0]: row[1] for row in rows}, bool(forced)

    numbers, is_forced = run_as_superuser(database_url, read)
    assert numbers == {ids[1]: 1, ids[2]: 2, ids[0]: 3}
    assert is_forced
