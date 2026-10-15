"""The custom-field library (MPS-8A.03, MPS-8A.04, MPS-8A.05, MPS-8A.06)."""

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
from relyxus_api.modules.incident.field_model import CustomFieldDefinition
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import ORG_A, WORKSPACE_B1, principal_for, seed_two_organisations_with_members

pytestmark = pytest.mark.integration
FIELDS = "/api/v1/custom-fields"
CHOICES = [{"value": "eu_west", "label": "EU West"}, {"value": "us_east", "label": "US East"}]


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
    payload = {"key": f"f_{uuid.uuid4().hex[:8]}", "label": "Region", "data_type": "text", **body}
    return client.post(FIELDS, headers=_headers(), json=payload)


def test_choice_field_with_condition_and_stage(client: TestClient) -> None:
    incident_type = client.post(
        "/api/v1/incident-types",
        headers=_headers(),
        json={"key": "payment-incident", "name": "Payment incident", "default_severity": "sev2"},
    ).json()["data"]

    created = _create(
        client,
        key="affected_region",
        data_type="single_choice",
        options=CHOICES,
        display_condition={
            "incident_type_ids": [incident_type["id"]],
            "severities": ["sev2", "sev1"],
        },
        required_at_stage="resolved",
    )

    data = created.json()["data"]
    assert created.status_code == 201
    assert (data["key"], data["data_type"], data["required_at_stage"], data["version"]) == (
        "affected_region",
        "single_choice",
        "resolved",
        1,
    )
    assert data["display_condition"] == {
        "incident_type_ids": [incident_type["id"]],
        "severities": ["sev1", "sev2"],
    }
    assert [option["value"] for option in data["options"]] == ["eu_west", "us_east"]


@pytest.mark.parametrize(
    "body",
    [
        {"data_type": "single_choice"},
        {"data_type": "multiple_choice", "options": [CHOICES[0], CHOICES[0]]},
        {"data_type": "text", "options": CHOICES},
        {"display_condition": {"incident_type_ids": [str(uuid.uuid4())]}},
    ],
)
def test_invalid_definitions_are_rejected(client: TestClient, body: dict[str, Any]) -> None:
    response = _create(client, **body)

    assert (response.status_code, response.json()["code"]) == (422, "CUSTOM_FIELD_INVALID")


@pytest.mark.parametrize(
    "body",
    [
        {"key": "Bad-Key"},
        {"data_type": "vendor"},
        {"required_at_stage": "triage"},
    ],
)
def test_schema_validation(client: TestClient, body: dict[str, Any]) -> None:
    assert _create(client, **body).status_code == 422


def test_changes_are_versioned_and_type_is_fixed(client: TestClient) -> None:
    field_id = _create(client, label="Before").json()["data"]["id"]

    updated = client.patch(
        f"{FIELDS}/{field_id}",
        headers=_headers(),
        json={"label": "After", "required_at_stage": "mitigating"},
    ).json()["data"]
    type_change = client.patch(
        f"{FIELDS}/{field_id}", headers=_headers(), json={"data_type": "number"}
    )
    versions = client.get(
        f"/api/v1/configuration/custom_field/{field_id}/versions", headers=_headers()
    ).json()["data"]

    assert (updated["label"], updated["version"]) == ("After", 2)
    assert type_change.status_code == 422
    assert versions[1]["difference"] == {
        "label": {"before": "Before", "after": "After"},
        "required_at_stage": {"before": None, "after": "mitigating"},
    }


def test_archive_keys_and_roles(client: TestClient) -> None:
    field_id = _create(client, key="archived_one").json()["data"]["id"]

    duplicate = _create(client, key="archived_one")
    by_commander = client.post(
        FIELDS,
        headers=_headers("sub-amira"),
        json={"key": "nope", "label": "x", "data_type": "text"},
    )
    archived = client.patch(f"{FIELDS}/{field_id}", headers=_headers(), json={"is_archived": True})
    listed = [
        item["id"] for item in client.get(f"{FIELDS}?limit=100", headers=_headers()).json()["data"]
    ]

    assert duplicate.json()["code"] == "CUSTOM_FIELD_KEY_TAKEN"
    assert by_commander.status_code == 403
    assert archived.json()["data"]["archived_at"] is not None
    assert field_id not in listed


def test_fields_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _create(client)

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(CustomFieldDefinition.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
