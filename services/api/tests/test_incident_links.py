"""Links between incidents (MPS-8A.31, MPS-20.31)."""

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
from relyxus_api.modules.audit.model import AuditEvent
from relyxus_api.modules.incident.link_model import IncidentLink
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
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


def _headers(*, workspace: uuid.UUID = WORKSPACE_B1, key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _incident(client: TestClient, workspace: uuid.UUID = WORKSPACE_B1) -> str:
    response = client.post(
        INCIDENTS,
        headers=_headers(workspace=workspace),
        json={"title": "Linked", "severity": "sev3"},
    )
    incident_id: str = response.json()["data"]["id"]
    return incident_id


def _link(
    client: TestClient, source: str, target: str, link_type: str, key: str | None = None
) -> Any:
    return client.post(
        f"{INCIDENTS}/{source}/links",
        headers=_headers(key=key),
        json={"target_incident_id": target, "link_type": link_type},
    )


def _links(client: TestClient, incident_id: str, query: str = "") -> Any:
    return client.get(f"{INCIDENTS}/{incident_id}/links{query}", headers=_headers()).json()


def _timeline_kinds(client: TestClient, incident_id: str) -> list[str]:
    events = client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()["data"]
    return [event["kind"] for event in events]


def test_link_reads_both_ways_and_shows_on_both_timelines(
    client: TestClient, database_url: str
) -> None:
    child, cause = _incident(client), _incident(client)

    created = _link(client, child, cause, "caused_by")

    link = created.json()["data"]
    assert created.status_code == 201
    assert (link["direction"], link["other_incident_id"], link["created_by_user_id"]) == (
        "outgoing",
        cause,
        str(AMIRA),
    )
    incoming = _links(client, cause)["data"]
    assert [(item["id"], item["direction"], item["other_incident_id"]) for item in incoming] == [
        (link["id"], "incoming", child)
    ]
    assert _timeline_kinds(client, child)[-1] == "incident.link_added"
    assert _timeline_kinds(client, cause)[-1] == "incident.link_added"

    async def audit_count(session: AsyncSession) -> int:
        query = select(AuditEvent.id).where(AuditEvent.target_id == link["id"])
        rows = await session.scalars(query)
        return len(rows.all())

    assert run_as_superuser(database_url, audit_count) == 1


def test_one_link_per_type_in_either_direction(client: TestClient) -> None:
    first, second = _incident(client), _incident(client)
    assert _link(client, first, second, "related_to").status_code == 201

    same = _link(client, first, second, "related_to")
    reverse = _link(client, second, first, "related_to")
    other_type = _link(client, second, first, "duplicate_of")

    assert (same.status_code, same.json()["code"]) == (409, "INCIDENT_LINK_EXISTS")
    assert reverse.json()["code"] == "INCIDENT_LINK_EXISTS"
    assert other_type.status_code == 201


def test_invalid_targets_are_rejected(client: TestClient) -> None:
    incident = _incident(client)
    elsewhere = _incident(client, WORKSPACE_A1)

    to_self = _link(client, incident, incident, "related_to")
    to_other_workspace = _link(client, incident, elsewhere, "related_to")
    to_unknown = _link(client, incident, str(uuid.uuid4()), "related_to")
    from_unknown = _link(client, str(uuid.uuid4()), incident, "related_to")
    bad_type = _link(client, incident, _incident(client), "parent_of")

    for response in (to_self, to_other_workspace, to_unknown):
        assert (response.status_code, response.json()["code"]) == (
            422,
            "INCIDENT_LINK_INVALID_TARGET",
        )
    assert from_unknown.json()["code"] == "INCIDENT_NOT_FOUND"
    assert bad_type.status_code == 422


def test_closed_targets_are_linkable_but_frozen_sources_are_not(client: TestClient) -> None:
    open_incident, cancelled = _incident(client), _incident(client)
    client.post(
        f"{INCIDENTS}/{cancelled}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "False alarm"},
    )

    to_cancelled = _link(client, open_incident, cancelled, "recurrence_of")
    from_cancelled = _link(client, cancelled, open_incident, "related_to")

    assert to_cancelled.status_code == 201
    assert (from_cancelled.status_code, from_cancelled.json()["code"]) == (
        409,
        "INCIDENT_NOT_EDITABLE",
    )


def test_remove_from_either_end(client: TestClient) -> None:
    source, target, unrelated = _incident(client), _incident(client), _incident(client)
    link_id = _link(client, source, target, "duplicate_of").json()["data"]["id"]

    wrong_incident = client.delete(f"{INCIDENTS}/{unrelated}/links/{link_id}", headers=_headers())
    removed = client.delete(f"{INCIDENTS}/{target}/links/{link_id}", headers=_headers())
    again = client.delete(f"{INCIDENTS}/{target}/links/{link_id}", headers=_headers())

    assert wrong_incident.json()["code"] == "INCIDENT_LINK_NOT_FOUND"
    assert removed.status_code == 204
    assert again.status_code == 404
    assert _links(client, source)["data"] == []
    assert _timeline_kinds(client, source)[-1] == "incident.link_removed"
    assert _timeline_kinds(client, target)[-1] == "incident.link_removed"


def test_list_pages_and_retry_replays(client: TestClient) -> None:
    hub = _incident(client)
    key = f"idem-{uuid.uuid4()}"
    first_target = _incident(client)
    first = _link(client, hub, first_target, "related_to", key)
    retry = _link(client, hub, first_target, "related_to", key)
    for _ in range(3):
        _link(client, hub, _incident(client), "related_to")

    page_one = _links(client, hub, "?limit=3")
    page_two = _links(client, hub, f"?limit=3&cursor={page_one['meta']['next_cursor']}")

    assert retry.json() == first.json()
    ids = [item["id"] for item in page_one["data"] + page_two["data"]]
    assert len(ids) == len(set(ids)) == 4
    assert page_two["meta"]["next_cursor"] is None


def test_links_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _link(client, _incident(client), _incident(client), "caused_by")

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentLink.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
