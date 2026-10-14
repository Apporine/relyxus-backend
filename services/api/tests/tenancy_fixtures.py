"""Shared seed data: two organisations, three workspaces, three users with role grants.

Amira holds responder + viewer in A1 and incident_commander in B1 (two organisations);
the suspended user holds viewer in A1; Bob holds admin in B1 only.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import User, WorkspaceMembership
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal

ISSUER = "https://id.example.test/realms/relyxus"
ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()
WORKSPACE_A1, WORKSPACE_A2, WORKSPACE_B1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
AMIRA, SUSPENDED, BOB = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
REGION = "eu-west-2"


def principal_for(subject: str, issuer: str = ISSUER) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        issuer=issuer, subject=subject, email=None, display_name=None, authenticated_at=None
    )


async def seed_two_organisations_with_members(session: AsyncSession) -> None:
    for org_id, name in ((ORG_A, "Alpha Bank"), (ORG_B, "Bravo Pay")):
        session.add(
            Organization(id=org_id, name=name, deployment_mode="saas", default_region=REGION)
        )
    await session.flush()
    for workspace_id, org_id, key, name in (
        (WORKSPACE_A1, ORG_A, "a-one", "Alpha Payments"),
        (WORKSPACE_A2, ORG_A, "a-two", "Alpha Cards"),
        (WORKSPACE_B1, ORG_B, "b-one", "Bravo Core"),
    ):
        session.add(
            Workspace(
                id=workspace_id,
                organization_id=org_id,
                key=key,
                name=name,
                data_residency_region=REGION,
            )
        )
    for user_id, subject, status in (
        (AMIRA, "sub-amira", "active"),
        (SUSPENDED, "sub-suspended", "suspended"),
        (BOB, "sub-bob", "active"),
    ):
        session.add(
            User(
                id=user_id,
                idp_issuer=ISSUER,
                idp_subject=subject,
                email=None,
                display_name=None,
                status=status,
            )
        )
    await session.flush()
    for org_id, workspace_id, user_id, role in (
        (ORG_A, WORKSPACE_A1, AMIRA, "responder"),
        (ORG_A, WORKSPACE_A1, AMIRA, "viewer"),
        (ORG_B, WORKSPACE_B1, AMIRA, "incident_commander"),
        (ORG_A, WORKSPACE_A1, SUSPENDED, "viewer"),
        (ORG_B, WORKSPACE_B1, BOB, "admin"),
    ):
        session.add(
            WorkspaceMembership(
                organization_id=org_id, workspace_id=workspace_id, user_id=user_id, role=role
            )
        )
