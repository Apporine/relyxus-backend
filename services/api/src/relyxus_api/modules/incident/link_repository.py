"""Incident link persistence. Queries only; rules live in the link service."""

import uuid

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.link_model import IncidentLink


class IncidentLinkRepository:
    async def add(self, session: AsyncSession, link: IncidentLink) -> IncidentLink:
        session.add(link)
        await session.flush()
        await session.refresh(link)
        return link

    async def find_between(
        self,
        session: AsyncSession,
        first_incident_id: uuid.UUID,
        second_incident_id: uuid.UUID,
        link_type: str,
    ) -> IncidentLink | None:
        """A link of this type between the two incidents, in either direction."""
        link: IncidentLink | None = await session.scalar(
            select(IncidentLink).where(
                IncidentLink.link_type == link_type,
                or_(
                    and_(
                        IncidentLink.from_incident_id == first_incident_id,
                        IncidentLink.to_incident_id == second_incident_id,
                    ),
                    and_(
                        IncidentLink.from_incident_id == second_incident_id,
                        IncidentLink.to_incident_id == first_incident_id,
                    ),
                ),
            )
        )
        return link

    async def find_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID, link_id: uuid.UUID
    ) -> IncidentLink | None:
        link: IncidentLink | None = await session.scalar(
            select(IncidentLink).where(
                IncidentLink.id == link_id,
                or_(
                    IncidentLink.from_incident_id == incident_id,
                    IncidentLink.to_incident_id == incident_id,
                ),
            )
        )
        return link

    async def list_for_incident(
        self,
        session: AsyncSession,
        incident_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[IncidentLink]:
        """Links in both directions, oldest first (UUIDv7 order), keyset after `after_id`."""
        query = select(IncidentLink).where(
            or_(
                IncidentLink.from_incident_id == incident_id,
                IncidentLink.to_incident_id == incident_id,
            )
        )
        if after_id is not None:
            query = query.where(IncidentLink.id > after_id)
        links = await session.scalars(query.order_by(IncidentLink.id).limit(limit))
        return list(links)

    async def remove(self, session: AsyncSession, link_id: uuid.UUID) -> None:
        await session.execute(delete(IncidentLink).where(IncidentLink.id == link_id))
