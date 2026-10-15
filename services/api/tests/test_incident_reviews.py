"""Post-incident reviews (MPS-8A.11, MPS-13.12, MPS-13.16, MPS-20.50)."""

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
from relyxus_api.modules.incident.review_model import IncidentReview
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    SUSPENDED,
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


def _headers(subject: str = "sub-amira", key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _move(client: TestClient, incident_id: str, *states: str) -> Any:
    response = None
    for state in states:
        response = client.post(
            f"{INCIDENTS}/{incident_id}/transitions",
            headers=_headers(),
            json={"target_state": state},
        )
    return response


def _resolved(
    client: TestClient, severity: str = "sev1", commander: uuid.UUID | None = None
) -> str:
    incident_id: str = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Reviewed", "severity": severity}
    ).json()["data"]["id"]
    if commander is not None:
        client.put(
            f"{INCIDENTS}/{incident_id}/roles/incident_commander",
            headers=_headers(),
            json={"user_id": str(commander)},
        )
    _move(client, incident_id, "mitigating", "monitoring", "resolved")
    return incident_id


def _review(client: TestClient, incident_id: str) -> Any:
    return client.get(f"{INCIDENTS}/{incident_id}/review", headers=_headers())


def _edit(client: TestClient, incident_id: str, subject: str = "sub-amira", **body: Any) -> Any:
    return client.patch(f"{INCIDENTS}/{incident_id}/review", headers=_headers(subject), json=body)


def _review_move(
    client: TestClient, incident_id: str, target: str, subject: str = "sub-amira"
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/review/transitions",
        headers=_headers(subject),
        json={"target_state": target},
    )


def test_resolving_creates_a_draft_owned_by_the_commander(client: TestClient) -> None:
    with_commander = _resolved(client, commander=BOB)
    without_commander = _resolved(client)

    review = _review(client, with_commander)

    data = review.json()["data"]
    assert review.status_code == 200
    assert review.headers["etag"]
    assert (data["state"], data["owner_user_id"], data["summary"]) == ("draft", str(BOB), "")
    assert _review(client, without_commander).json()["data"]["owner_user_id"] == str(AMIRA)
    kinds = [
        event["kind"]
        for event in client.get(
            f"{INCIDENTS}/{with_commander}/timeline", headers=_headers()
        ).json()["data"]
    ]
    assert kinds[-2:] == ["incident.transitioned", "incident.review_created"]


def test_no_review_before_resolution_and_reopen_keeps_it(client: TestClient) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Open", "severity": "sev2"}
    ).json()["data"]["id"]
    assert _review(client, incident_id).json()["code"] == "INCIDENT_REVIEW_NOT_FOUND"

    _move(client, incident_id, "mitigating", "monitoring", "resolved")
    first_id = _review(client, incident_id).json()["data"]["id"]
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "investigating", "reason": "Errors returned"},
    )
    _move(client, incident_id, "mitigating", "monitoring", "resolved")

    assert _review(client, incident_id).json()["data"]["id"] == first_id


def test_review_lifecycle_with_content_rules(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1")

    empty = _review_move(client, incident_id, "in_review")
    _edit(client, incident_id, summary="Processor TLS certificate expired.")
    no_lessons = _review_move(client, incident_id, "in_review")
    _edit(client, incident_id, lessons_learned="Monitor certificate expiry.")
    submitted = _review_move(client, incident_id, "in_review")
    sent_back = _review_move(client, incident_id, "draft")
    _review_move(client, incident_id, "in_review")
    approved = _review_move(client, incident_id, "approved")
    locked = _edit(client, incident_id, summary="Changed after approval")
    published = _review_move(client, incident_id, "published")
    closed_directly = _review_move(client, incident_id, "closed")

    assert empty.json()["code"] == "INCIDENT_REVIEW_CONTENT_REQUIRED"
    assert no_lessons.json()["code"] == "INCIDENT_REVIEW_CONTENT_REQUIRED"
    assert submitted.json()["data"]["submitted_at"] is not None
    assert sent_back.json()["data"]["state"] == "draft"
    assert approved.json()["data"]["approved_at"] is not None
    assert (locked.status_code, locked.json()["code"]) == (409, "INCIDENT_REVIEW_NOT_EDITABLE")
    assert published.json()["data"]["state"] == "published"
    assert (closed_directly.status_code, closed_directly.json()["code"]) == (
        409,
        "INCIDENT_REVIEW_INVALID_TRANSITION",
    )


def test_lessons_are_optional_below_sev2(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3")
    _edit(client, incident_id, summary="Minor latency.")

    assert _review_move(client, incident_id, "in_review").json()["data"]["state"] == "in_review"


def test_only_the_review_owner_moves_it_and_owner_changes_are_checked(
    client: TestClient,
) -> None:
    incident_id = _resolved(client, "sev3")
    _edit(client, incident_id, summary="Owner rules.")

    by_other = _review_move(client, incident_id, "in_review", subject="sub-bob")
    not_member = _edit(client, incident_id, owner_user_id=str(SUSPENDED))
    reassigned = _edit(client, incident_id, owner_user_id=str(BOB))
    by_new_owner = _review_move(client, incident_id, "in_review", subject="sub-bob")
    by_old_owner = _review_move(client, incident_id, "approved")

    assert (by_other.status_code, by_other.json()["code"]) == (403, "INSUFFICIENT_WORKSPACE_ROLE")
    assert not_member.json()["code"] == "INCIDENT_REVIEW_OWNER_NOT_MEMBER"
    assert reassigned.json()["data"]["owner_user_id"] == str(BOB)
    assert by_new_owner.json()["data"]["state"] == "in_review"
    assert by_old_owner.status_code == 403


def test_start_for_earlier_incidents_and_stale_etag(client: TestClient, database_url: str) -> None:
    incident_id = _resolved(client, "sev3")
    existing = _review(client, incident_id)

    async def drop_review(session: AsyncSession) -> None:
        review = await session.scalar(
            select(IncidentReview).where(IncidentReview.incident_id == uuid.UUID(incident_id))
        )
        await session.delete(review)

    duplicate = client.post(f"{INCIDENTS}/{incident_id}/review", headers=_headers())
    run_as_superuser(database_url, drop_review)
    started = client.post(f"{INCIDENTS}/{incident_id}/review", headers=_headers())
    stale = client.patch(
        f"{INCIDENTS}/{incident_id}/review",
        headers={**_headers(), "If-Match": existing.headers["etag"]},
        json={"summary": "Stale"},
    )

    assert duplicate.json()["code"] == "INCIDENT_REVIEW_EXISTS"
    assert (started.status_code, started.json()["data"]["state"]) == (201, "draft")
    assert stale.status_code == 412


def test_reviews_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _resolved(client)

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentReview.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
