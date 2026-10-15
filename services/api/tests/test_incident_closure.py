"""The closure gate (MPS-8A.12, MPS-13.04, MPS-13.17)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.access.model import User, WorkspaceMembership
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
CAROL = uuid.uuid4()


async def _seed_workspace_owner(session: AsyncSession) -> None:
    session.add(
        User(
            id=CAROL,
            idp_issuer=ISSUER,
            idp_subject="sub-carol",
            email=None,
            display_name=None,
            status="active",
        )
    )
    await session.flush()
    session.add(
        WorkspaceMembership(
            organization_id=ORG_B, workspace_id=WORKSPACE_B1, user_id=CAROL, role="owner"
        )
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    run_as_superuser(url, _seed_workspace_owner)
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


def _move(
    client: TestClient, incident_id: str, target: str, subject: str = "sub-amira", **body: Any
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(subject),
        json={"target_state": target, **body},
    )


def _resolved(client: TestClient, severity: str) -> str:
    incident_id: str = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Closure", "severity": severity}
    ).json()["data"]["id"]
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/incident_commander",
        headers=_headers(),
        json={"user_id": str(AMIRA)},
    )
    for state in ("mitigating", "monitoring", "resolved"):
        _move(client, incident_id, state)
    return incident_id


def _approve_review(client: TestClient, incident_id: str) -> None:
    review = f"{INCIDENTS}/{incident_id}/review"
    client.patch(
        review,
        headers=_headers(),
        json={"summary": "Gateway certificate expired.", "lessons_learned": "Track expiry."},
    )
    for target in ("in_review",):
        client.post(f"{review}/transitions", headers=_headers(), json={"target_state": target})
    client.post(f"{review}/sign-off", headers=_headers())
    approved = client.post(
        f"{review}/transitions", headers=_headers(), json={"target_state": "approved"}
    )
    assert approved.json()["data"]["state"] == "approved"


def _code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


def test_sev1_closes_with_signed_off_review_and_root_cause(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1")
    _approve_review(client, incident_id)

    no_root_cause = _move(client, incident_id, "closed")
    closed = _move(client, incident_id, "closed", root_cause="Expired gateway certificate")

    assert _code(no_root_cause) == (422, "INCIDENT_ROOT_CAUSE_REQUIRED")
    data = closed.json()["data"]
    assert (data["lifecycle_state"], data["root_cause"], data["closed_by_user_id"]) == (
        "closed",
        "Expired gateway certificate",
        str(AMIRA),
    )
    assert data["closed_at"] is not None
    review = client.get(f"{INCIDENTS}/{incident_id}/review", headers=_headers()).json()["data"]
    assert (review["state"], review["closed_at"] is not None) == ("closed", True)
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds[-2:] == ["incident.transitioned", "incident.review_transitioned"]


def test_review_must_be_approved_first(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3")

    assert _code(_move(client, incident_id, "closed")) == (409, "INCIDENT_REVIEW_REQUIRED")


def test_unfinished_tasks_block_closing(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3")
    task_id = client.post(
        f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json={"title": "Leftover"}
    ).json()["data"]["id"]
    _approve_review(client, incident_id)

    blocked = _move(client, incident_id, "closed")
    client.post(f"{INCIDENTS}/{incident_id}/tasks/{task_id}/follow-up", headers=_headers(), json={})
    closed = _move(client, incident_id, "closed")

    assert _code(blocked) == (409, "INCIDENT_UNFINISHED_TASKS")
    assert task_id in blocked.json()["detail"]
    assert closed.json()["data"]["lifecycle_state"] == "closed"


def test_mandatory_follow_ups_need_owner_and_due_date(client: TestClient) -> None:
    incident_id = _resolved(client, "sev2")
    follow_up_id = client.post(
        f"{INCIDENTS}/{incident_id}/follow-ups",
        headers=_headers(),
        json={"title": "Automate certificate renewal", "owner_user_id": str(BOB)},
    ).json()["data"]["id"]
    _approve_review(client, incident_id)

    blocked = _move(client, incident_id, "closed", root_cause="Manual renewal missed")
    client.patch(
        f"{INCIDENTS}/{incident_id}/follow-ups/{follow_up_id}",
        headers=_headers(),
        json={"due_at": "2026-12-01T09:00:00Z"},
    )
    closed = _move(client, incident_id, "closed", root_cause="Manual renewal missed")

    assert _code(blocked) == (409, "INCIDENT_FOLLOW_UPS_INCOMPLETE")
    assert closed.json()["data"]["lifecycle_state"] == "closed"


def test_only_review_owner_or_workspace_owner_closes(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3")
    _approve_review(client, incident_id)

    by_admin = _move(client, incident_id, "closed", subject="sub-bob")
    by_owner = _move(client, incident_id, "closed", subject="sub-carol")

    assert _code(by_admin) == (403, "INSUFFICIENT_WORKSPACE_ROLE")
    assert by_owner.json()["data"]["closed_by_user_id"] == str(CAROL)


def test_owner_exception_skips_gates_but_not_root_cause(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1")
    exception = "Vendor-side incident; review held by the vendor."

    by_review_owner = _move(client, incident_id, "closed", closure_exception_reason=exception)
    without_root_cause = _move(
        client, incident_id, "closed", subject="sub-carol", closure_exception_reason=exception
    )
    closed = _move(
        client,
        incident_id,
        "closed",
        subject="sub-carol",
        closure_exception_reason=exception,
        root_cause="Upstream processor outage",
    )

    assert _code(by_review_owner) == (403, "INSUFFICIENT_WORKSPACE_ROLE")
    assert _code(without_root_cause) == (422, "INCIDENT_ROOT_CAUSE_REQUIRED")
    data = closed.json()["data"]
    assert (data["lifecycle_state"], data["closure_exception_reason"]) == ("closed", exception)
    review = client.get(f"{INCIDENTS}/{incident_id}/review", headers=_headers()).json()["data"]
    assert review["state"] == "draft"
    last = client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()["data"][-1]
    assert last["after"]["closure_exception_reason"] == exception


def test_closed_incident_still_tracks_follow_ups(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3")
    _approve_review(client, incident_id)
    _move(client, incident_id, "closed")

    follow_up = client.post(
        f"{INCIDENTS}/{incident_id}/follow-ups", headers=_headers(), json={"title": "Later work"}
    )
    task = client.post(f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json={"title": "x"})

    assert follow_up.status_code == 201
    assert _code(task) == (409, "INCIDENT_NOT_EDITABLE")
