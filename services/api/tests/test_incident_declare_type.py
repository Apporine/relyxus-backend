"""Declaring under an incident type (MPS-8A.06, MPS-8A.08, MPS-20.12; register Q-44)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
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


def _headers(subject: str = "sub-amira", workspace: uuid.UUID = WORKSPACE_B1) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _type(client: TestClient, **body: Any) -> dict[str, Any]:
    payload = {
        "key": f"type-{uuid.uuid4().hex[:8]}",
        "name": "Payment incident",
        "allowed_severities": ["sev1", "sev2"],
        "default_severity": "sev2",
        **body,
    }
    data: dict[str, Any] = client.post(TYPES, headers=_headers("sub-bob"), json=payload).json()[
        "data"
    ]
    return data


def _declare(client: TestClient, workspace: uuid.UUID = WORKSPACE_B1, **body: Any) -> Any:
    return client.post(
        INCIDENTS, headers=_headers(workspace=workspace), json={"title": "Cards", **body}
    )


def test_declaring_without_types_still_needs_a_severity(client: TestClient) -> None:
    missing = _declare(client, WORKSPACE_A1)
    declared = _declare(client, WORKSPACE_A1, severity="sev3")

    assert (missing.status_code, missing.json()["code"]) == (422, "INCIDENT_SEVERITY_REQUIRED")
    data = declared.json()["data"]
    assert (data["severity"], data["incident_type_id"], data["visibility"]) == (
        "sev3",
        None,
        "workspace",
    )


def test_type_supplies_defaults_and_records_its_version(client: TestClient) -> None:
    payment = _type(client, default_visibility="restricted")

    declared = _declare(client, incident_type_id=payment["id"]).json()["data"]
    explicit = _declare(
        client, incident_type_id=payment["id"], severity="sev1", visibility="workspace"
    ).json()["data"]

    assert (declared["severity"], declared["visibility"]) == ("sev2", "restricted")
    assert (declared["incident_type_id"], declared["incident_type_version"]) == (
        payment["id"],
        1,
    )
    assert (explicit["severity"], explicit["visibility"]) == ("sev1", "workspace")


def test_types_become_required_once_the_workspace_has_one(client: TestClient) -> None:
    _type(client)

    response = _declare(client, severity="sev3")

    assert (response.status_code, response.json()["code"]) == (422, "INCIDENT_TYPE_REQUIRED")


def test_severity_must_be_allowed_and_archived_types_refused(client: TestClient) -> None:
    payment = _type(client)
    archived = _type(client)
    client.patch(
        f"{TYPES}/{archived['id']}", headers=_headers("sub-bob"), json={"is_archived": True}
    )

    not_allowed = _declare(client, incident_type_id=payment["id"], severity="sev4")
    unusable = _declare(client, incident_type_id=archived["id"])
    unknown = _declare(client, incident_type_id=str(uuid.uuid4()))

    assert not_allowed.json()["code"] == "INCIDENT_SEVERITY_NOT_ALLOWED"
    for response in (unusable, unknown):
        assert response.json()["code"] == "INCIDENT_TYPE_INVALID"


def test_later_type_edits_do_not_change_declared_incidents(client: TestClient) -> None:
    payment = _type(client)
    incident_id = _declare(client, incident_type_id=payment["id"]).json()["data"]["id"]
    client.patch(
        f"{TYPES}/{payment['id']}",
        headers=_headers("sub-bob"),
        json={"allowed_severities": ["sev1", "sev2", "sev3"]},
    )

    to_sev3 = client.patch(
        f"{INCIDENTS}/{incident_id}",
        headers=_headers(),
        json={"severity": "sev3", "reason": "Fewer customers affected"},
    )
    to_sev1 = client.patch(
        f"{INCIDENTS}/{incident_id}",
        headers=_headers(),
        json={"severity": "sev1", "reason": "Spreading"},
    )
    incident = client.get(f"{INCIDENTS}/{incident_id}", headers=_headers()).json()["data"]

    assert to_sev3.json()["code"] == "INCIDENT_SEVERITY_NOT_ALLOWED"
    assert to_sev1.status_code == 200
    assert incident["incident_type_version"] == 1


def test_list_incidents_by_type(client: TestClient) -> None:
    payment, outage = _type(client), _type(client, name="Outage")
    on_payment = _declare(client, incident_type_id=payment["id"]).json()["data"]["id"]
    _declare(client, incident_type_id=outage["id"])

    listed = client.get(f"{INCIDENTS}?incident_type_id={payment['id']}", headers=_headers()).json()

    assert [item["id"] for item in listed["data"]] == [on_payment]
