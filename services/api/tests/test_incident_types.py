"""Incident types (MPS-8A.01, MPS-8A.02, MPS-8A.06, MPS-20.26)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import (
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.incident.type_model import IncidentType
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    ORG_A,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
TYPES = "/api/v1/incident-types"


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


def _headers(subject: str = "sub-bob") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _create(client: TestClient, **body: Any) -> Any:
    payload = {
        "key": f"type-{uuid.uuid4().hex[:8]}",
        "name": "Card outage",
        "allowed_severities": ["sev1", "sev2"],
        "default_severity": "sev2",
        **body,
    }
    return client.post(TYPES, headers=_headers(), json=payload)


def test_install_defaults_is_idempotent(client: TestClient) -> None:
    first = client.post(f"{TYPES}/defaults", headers=_headers()).json()["data"]
    second = client.post(f"{TYPES}/defaults", headers=_headers()).json()["data"]

    by_key = {item["key"]: item for item in first}
    assert len(first) == 9
    assert second == []
    assert by_key["security-event"]["default_visibility"] == "invite_only"
    assert by_key["data-incident"]["default_visibility"] == "restricted"
    assert by_key["production-outage"]["allowed_severities"] == ["sev1", "sev2", "sev3", "sev4"]
    assert {item["version"] for item in first} == {1}


def test_create_and_version_changes(client: TestClient) -> None:
    created = _create(client, allowed_severities=["sev2", "sev1", "sev1"])
    type_id = created.json()["data"]["id"]

    updated = client.patch(
        f"{TYPES}/{type_id}",
        headers=_headers(),
        json={"allowed_severities": ["sev1", "sev2", "sev3"], "default_visibility": "restricted"},
    ).json()["data"]
    versions = client.get(
        f"/api/v1/configuration/incident_type/{type_id}/versions", headers=_headers("sub-amira")
    ).json()["data"]

    assert created.json()["data"]["allowed_severities"] == ["sev1", "sev2"]
    assert updated["version"] == 2
    assert [version["version"] for version in versions] == [1, 2]
    assert versions[1]["difference"]["default_visibility"] == {
        "before": "workspace",
        "after": "restricted",
    }


def test_default_severity_must_be_allowed(client: TestClient) -> None:
    rejected = _create(client, default_severity="sev4")
    type_id = _create(client).json()["data"]["id"]
    narrowed = client.patch(
        f"{TYPES}/{type_id}", headers=_headers(), json={"allowed_severities": ["sev1"]}
    )

    assert rejected.json()["code"] == "INCIDENT_TYPE_DEFAULT_SEVERITY_NOT_ALLOWED"
    assert narrowed.json()["code"] == "INCIDENT_TYPE_DEFAULT_SEVERITY_NOT_ALLOWED"


def test_rules_for_keys_roles_and_no_ops(client: TestClient) -> None:
    created = _create(client, key="unique-type").json()["data"]

    duplicate = _create(client, key="unique-type")
    by_commander = client.post(
        TYPES,
        headers=_headers("sub-amira"),
        json={"key": "nope", "name": "Nope", "default_severity": "sev3"},
    )
    no_op = client.patch(
        f"{TYPES}/{created['id']}", headers=_headers(), json={"name": "Card outage"}
    )
    empty = _create(client, allowed_severities=[])

    assert duplicate.json()["code"] == "INCIDENT_TYPE_KEY_TAKEN"
    assert by_commander.status_code == 403
    assert no_op.json()["code"] == "INCIDENT_TYPE_NO_CHANGES"
    assert empty.status_code == 422


def test_archive_hides_from_list(client: TestClient) -> None:
    type_id = _create(client).json()["data"]["id"]

    client.patch(f"{TYPES}/{type_id}", headers=_headers(), json={"is_archived": True})

    visible = [
        item["id"] for item in client.get(f"{TYPES}?limit=100", headers=_headers()).json()["data"]
    ]
    archived = [
        item["id"]
        for item in client.get(
            f"{TYPES}?limit=100&include_archived=true", headers=_headers()
        ).json()["data"]
    ]
    assert type_id not in visible
    assert type_id in archived
    assert client.get(f"{TYPES}/{type_id}", headers=_headers()).json()["data"]["archived_at"]


def test_types_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _create(client)

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentType.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
