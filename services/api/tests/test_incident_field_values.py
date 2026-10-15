"""Custom field values on incidents (MPS-8A.04, MPS-8A.05, MPS-20.28)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.access.model import WorkspaceMembership
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
FIELDS = "/api/v1/custom-fields"


async def _make_amira_lead_in_a1(session: AsyncSession) -> None:
    for role in ("admin", "incident_commander"):
        session.add(
            WorkspaceMembership(
                organization_id=ORG_A, workspace_id=WORKSPACE_A1, user_id=AMIRA, role=role
            )
        )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    run_as_superuser(url, _make_amira_lead_in_a1)
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


def _field(client: TestClient, workspace: uuid.UUID = WORKSPACE_B1, **body: Any) -> str:
    subject = "sub-bob" if workspace == WORKSPACE_B1 else "sub-amira"
    payload = {"key": f"f_{uuid.uuid4().hex[:8]}", "label": "Field", "data_type": "text", **body}
    response = client.post(FIELDS, headers=_headers(subject, workspace), json=payload)
    key: str = response.json()["data"]["key"]
    return key


def _declare(client: TestClient, **body: Any) -> Any:
    return client.post(
        INCIDENTS, headers=_headers(), json={"title": "Fields", "severity": "sev2", **body}
    )


def _set(client: TestClient, incident_id: str, key: str, value: Any) -> Any:
    return client.put(
        f"{INCIDENTS}/{incident_id}/fields/{key}", headers=_headers(), json={"value": value}
    )


@pytest.mark.parametrize(
    ("definition", "given", "stored"),
    [
        ({"data_type": "text"}, "  EU card rails  ", "EU card rails"),
        ({"data_type": "number"}, 12.50, "12.5"),
        ({"data_type": "number"}, "1000", "1000"),
        (
            {"data_type": "currency"},
            {"amount_minor": 125000, "currency": "EUR"},
            {"amount_minor": 125000, "currency": "EUR"},
        ),
        ({"data_type": "date_time"}, "2026-10-15T10:00:00+05:00", "2026-10-15T05:00:00+00:00"),
        ({"data_type": "yes_no"}, True, True),
        ({"data_type": "url"}, "https://status.example.com/x", "https://status.example.com/x"),
        (
            {
                "data_type": "multiple_choice",
                "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
            },
            ["b", "a"],
            ["a", "b"],
        ),
        ({"data_type": "user"}, str(BOB), str(BOB)),
    ],
)
def test_values_are_validated_and_normalised(
    client: TestClient, definition: dict[str, Any], given: Any, stored: Any
) -> None:
    key = _field(client, **definition)
    incident_id = _declare(client).json()["data"]["id"]

    response = _set(client, incident_id, key, given)

    assert response.status_code == 200
    assert response.json()["data"]["value"] == stored


@pytest.mark.parametrize(
    ("definition", "given"),
    [
        ({"data_type": "number"}, True),
        ({"data_type": "number"}, "NaN"),
        ({"data_type": "currency"}, {"amount_minor": 1.5, "currency": "EUR"}),
        ({"data_type": "currency"}, {"amount_minor": 1, "currency": "euro"}),
        ({"data_type": "date_time"}, "2026-10-15T10:00:00"),
        ({"data_type": "yes_no"}, "yes"),
        ({"data_type": "url"}, "ftp://files.example.com"),
        ({"data_type": "single_choice", "options": [{"value": "a", "label": "A"}]}, "z"),
        ({"data_type": "user"}, str(uuid.uuid4())),
        ({"data_type": "service"}, str(uuid.uuid4())),
    ],
)
def test_invalid_values_are_rejected(
    client: TestClient, definition: dict[str, Any], given: Any
) -> None:
    key = _field(client, **definition)
    incident_id = _declare(client).json()["data"]["id"]

    response = _set(client, incident_id, key, given)

    assert (response.status_code, response.json()["code"]) == (
        422,
        "INCIDENT_FIELD_VALUE_INVALID",
    )


def test_set_clear_and_history(client: TestClient) -> None:
    key = _field(client)
    incident_id = _declare(client).json()["data"]["id"]

    _set(client, incident_id, key, "first")
    _set(client, incident_id, key, "second")
    _set(client, incident_id, key, "second")
    cleared = client.delete(f"{INCIDENTS}/{incident_id}/fields/{key}", headers=_headers())
    again = client.delete(f"{INCIDENTS}/{incident_id}/fields/{key}", headers=_headers())

    assert cleared.status_code == 204
    assert again.json()["code"] == "INCIDENT_FIELD_VALUE_NOT_FOUND"
    events = client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()["data"]
    field_events = [(event["kind"], event["before"], event["after"]) for event in events[1:]]
    assert [kind for kind, _, _ in field_events] == [
        "incident.field_set",
        "incident.field_set",
        "incident.field_cleared",
    ]
    assert field_events[1][1] == {"key": key, "value": "first"}
    assert field_events[1][2] == {"key": key, "value": "second", "field_version": 1}


def test_display_conditions_decide_applicability(client: TestClient) -> None:
    key = _field(client, display_condition={"severities": ["sev1"]})
    incident_id = _declare(client).json()["data"]["id"]

    response = _set(client, incident_id, key, "x")

    assert response.json()["code"] == "INCIDENT_FIELD_NOT_APPLICABLE"


def test_required_fields_gate_declaration_and_transitions(client: TestClient) -> None:
    # Separate workspace (A1), so other tests' fields don't apply.
    to_declare = _field(client, WORKSPACE_A1, required_at_stage="investigating")
    to_monitor = _field(client, WORKSPACE_A1, required_at_stage="monitoring")
    a1 = WORKSPACE_A1

    missing = client.post(
        INCIDENTS, headers=_headers(workspace=a1), json={"title": "x", "severity": "sev2"}
    )
    declared = client.post(
        INCIDENTS,
        headers=_headers(workspace=a1),
        json={"title": "x", "severity": "sev2", "field_values": {to_declare: "known"}},
    )
    incident_id = declared.json()["data"]["id"]
    move = f"{INCIDENTS}/{incident_id}/transitions"
    mitigating = client.post(
        move, headers=_headers(workspace=a1), json={"target_state": "mitigating"}
    )
    blocked = client.post(move, headers=_headers(workspace=a1), json={"target_state": "monitoring"})
    client.put(
        f"{INCIDENT_PATH(incident_id)}/fields/{to_monitor}",
        headers=_headers(workspace=a1),
        json={"value": "done"},
    )
    monitoring = client.post(
        move, headers=_headers(workspace=a1), json={"target_state": "monitoring"}
    )

    assert (missing.status_code, missing.json()["code"]) == (
        422,
        "INCIDENT_REQUIRED_FIELDS_MISSING",
    )
    assert to_declare in missing.json()["detail"]
    assert declared.status_code == 201
    assert mitigating.status_code == 200
    assert blocked.json()["code"] == "INCIDENT_REQUIRED_FIELDS_MISSING"
    assert monitoring.status_code == 200


def INCIDENT_PATH(incident_id: str) -> str:  # noqa: N802
    return f"{INCIDENTS}/{incident_id}"


def test_archived_fields_keep_values_but_cannot_be_set(client: TestClient) -> None:
    key = _field(client)
    incident_id = _declare(client, field_values={key: "kept"}).json()["data"]["id"]
    field_id = client.get(f"{FIELDS}?limit=100", headers=_headers()).json()["data"]
    target = next(item["id"] for item in field_id if item["key"] == key)
    client.patch(f"{FIELDS}/{target}", headers=_headers("sub-bob"), json={"is_archived": True})

    listed = client.get(f"{INCIDENTS}/{incident_id}/fields", headers=_headers()).json()["data"]
    refused = _set(client, incident_id, key, "new")

    assert [(item["key"], item["value"], item["is_field_archived"]) for item in listed] == [
        (key, "kept", True)
    ]
    assert refused.json()["code"] == "INCIDENT_FIELD_VALUE_INVALID"
