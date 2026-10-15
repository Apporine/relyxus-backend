"""Incident visibility modes and access grants (MPS-8A.23, MPS-8A.24, MPS-20.30)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.access.model import User, WorkspaceMembership
from relyxus_api.modules.incident.access_grant_model import IncidentAccessGrant
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ISSUER,
    ORG_B,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
CAROL, DAN = uuid.uuid4(), uuid.uuid4()


async def _seed_owner_and_viewer(session: AsyncSession) -> None:
    for user_id, subject in ((CAROL, "sub-carol"), (DAN, "sub-dan")):
        session.add(
            User(
                id=user_id,
                idp_issuer=ISSUER,
                idp_subject=subject,
                email=None,
                display_name=None,
                status="active",
            )
        )
    await session.flush()
    for user_id, role in ((CAROL, "owner"), (DAN, "viewer")):
        session.add(
            WorkspaceMembership(
                organization_id=ORG_B, workspace_id=WORKSPACE_B1, user_id=user_id, role=role
            )
        )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    run_as_superuser(url, _seed_owner_and_viewer)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _headers(subject: str = "sub-amira") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _declare(client: TestClient, subject: str = "sub-amira", visibility: str = "restricted") -> str:
    incident_id: str = client.post(
        INCIDENTS,
        headers=_headers(subject),
        json={"title": "Insider fraud", "severity": "sev1", "visibility": visibility},
    ).json()["data"]["id"]
    return incident_id


def _sees(client: TestClient, subject: str, incident_id: str) -> bool:
    response = client.get(f"{INCIDENTS}/{incident_id}", headers=_headers(subject))
    assert response.status_code in {200, 404}
    return response.status_code == 200


def _grant(client: TestClient, incident_id: str, **body: Any) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/access-grants",
        headers=_headers(),
        json={"reason": "Needs to help", **body},
    )


def test_restricted_incident_is_invisible_everywhere(client: TestClient) -> None:
    incident_id = _declare(client)

    assert _sees(client, "sub-amira", incident_id)
    assert _sees(client, "sub-carol", incident_id)
    assert not _sees(client, "sub-bob", incident_id)
    listed = client.get(INCIDENTS, headers=_headers("sub-bob")).json()["data"]
    assert incident_id not in [item["id"] for item in listed]
    for path in ("tasks", "timeline", "roles", "services", "links"):
        response = client.get(f"{INCIDENTS}/{incident_id}/{path}", headers=_headers("sub-bob"))
        assert (path, response.json()["code"]) == (path, "INCIDENT_NOT_FOUND")
    patch = client.patch(
        f"{INCIDENTS}/{incident_id}", headers=_headers("sub-bob"), json={"title": "x"}
    )
    assert patch.json()["code"] == "INCIDENT_NOT_FOUND"


def test_person_grant_and_revoke(client: TestClient) -> None:
    incident_id = _declare(client)

    grant = _grant(client, incident_id, user_id=str(BOB))

    assert grant.status_code == 201
    assert _sees(client, "sub-bob", incident_id)
    revoked = client.delete(
        f"{INCIDENTS}/{incident_id}/access-grants/{grant.json()['data']['id']}", headers=_headers()
    )
    assert revoked.status_code == 204
    assert not _sees(client, "sub-bob", incident_id)


def test_team_and_role_grants_count_only_while_restricted(client: TestClient) -> None:
    team_id = client.post(
        "/api/v1/teams",
        headers=_headers("sub-bob"),
        json={"key": f"fraud-{uuid.uuid4().hex[:6]}", "name": "Fraud"},
    ).json()["data"]["id"]
    client.put(f"/api/v1/teams/{team_id}/members/{DAN}", headers=_headers("sub-bob"))
    by_team, by_role = _declare(client), _declare(client)
    _grant(client, by_team, team_id=team_id)
    _grant(client, by_role, role="viewer")

    assert _sees(client, "sub-dan", by_team)
    assert _sees(client, "sub-dan", by_role)

    for incident_id in (by_team, by_role):
        client.put(
            f"{INCIDENTS}/{incident_id}/visibility",
            headers=_headers(),
            json={"visibility": "invite_only", "reason": "Narrowing"},
        )
        assert not _sees(client, "sub-dan", incident_id)
    _grant(client, by_team, user_id=str(DAN))
    assert _sees(client, "sub-dan", by_team)


def test_expired_grants_do_not_count(client: TestClient, database_url: str) -> None:
    incident_id = _declare(client)

    async def expired_grant(session: AsyncSession) -> None:
        session.add(
            IncidentAccessGrant(
                id=uuid.uuid4(),
                organization_id=ORG_B,
                workspace_id=WORKSPACE_B1,
                incident_id=uuid.UUID(incident_id),
                user_id=BOB,
                reason="Old",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
                granted_by_user_id=AMIRA,
            )
        )

    run_as_superuser(database_url, expired_grant)

    assert not _sees(client, "sub-bob", incident_id)


def test_incident_role_holders_see_restricted_incidents(client: TestClient) -> None:
    incident_id = _declare(client)
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/scribe", headers=_headers(), json={"user_id": str(DAN)}
    )

    assert _sees(client, "sub-dan", incident_id)


def test_restricting_keeps_the_actor_in_and_is_on_the_timeline(client: TestClient) -> None:
    incident_id = _declare(client, "sub-bob", visibility="workspace")

    changed = client.put(
        f"{INCIDENTS}/{incident_id}/visibility",
        headers=_headers(),
        json={"visibility": "confidential", "reason": "Legal hold"},
    )
    unchanged = client.put(
        f"{INCIDENTS}/{incident_id}/visibility",
        headers=_headers(),
        json={"visibility": "confidential", "reason": "Again"},
    )

    assert changed.json()["data"]["visibility"] == "confidential"
    assert unchanged.json()["code"] == "INCIDENT_VISIBILITY_UNCHANGED"
    assert _sees(client, "sub-amira", incident_id)
    assert _sees(client, "sub-bob", incident_id)
    assert not _sees(client, "sub-dan", incident_id)
    grants = client.get(f"{INCIDENTS}/{incident_id}/access-grants", headers=_headers()).json()
    assert [grant["user_id"] for grant in grants["data"]] == [str(AMIRA)]
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds[-2:] == ["incident.access_granted", "incident.visibility_changed"]


def test_only_owners_and_commanders_manage_visibility(client: TestClient) -> None:
    incident_id = _declare(client, "sub-bob", visibility="workspace")

    by_admin = client.put(
        f"{INCIDENTS}/{incident_id}/visibility",
        headers=_headers("sub-bob"),
        json={"visibility": "restricted", "reason": "x"},
    )
    by_owner = client.put(
        f"{INCIDENTS}/{incident_id}/visibility",
        headers=_headers("sub-carol"),
        json={"visibility": "restricted", "reason": "x"},
    )

    assert (by_admin.status_code, by_admin.json()["code"]) == (403, "INSUFFICIENT_WORKSPACE_ROLE")
    assert by_owner.json()["data"]["visibility"] == "restricted"


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": str(uuid.uuid4())},
        {"team_id": str(uuid.uuid4())},
        {"user_id": str(BOB), "expires_at": "2020-01-01T00:00:00Z"},
        {"user_id": str(BOB), "role": "viewer"},
        {},
    ],
)
def test_invalid_grants_are_rejected(client: TestClient, body: dict[str, str]) -> None:
    response = _grant(client, _declare(client), **body)

    assert response.status_code == 422


def test_workspace_incidents_stay_visible_to_all(client: TestClient) -> None:
    incident_id = _declare(client, visibility="workspace")

    assert all(_sees(client, subject, incident_id) for subject in ("sub-bob", "sub-dan"))
