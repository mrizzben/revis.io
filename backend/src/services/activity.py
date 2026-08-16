"""Activity / audit history service (T6).

Append-only project events. `record_event` never mutates or deletes prior
rows; timeline reads apply the same visibility rules as the underlying
entities (client timelines only see events recorded with visibility="client").
"""

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.activity import ActivityEvent
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    project_id: int,
    actor_id: int,
    event_type: str,
    entity_type: str,
    entity_id: str | int | None = None,
    payload: dict[str, Any] | None = None,
    visibility: str = "internal",
) -> ActivityEvent:
    """Append one immutable activity event."""
    event = ActivityEvent(
        project_id=project_id,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        payload=payload or {},
        visibility=visibility,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


def _serialize_event(event: ActivityEvent, actor: User | None) -> dict[str, Any]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    return {
        "id": event.id,
        "project_id": event.project_id,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "payload": payload,
        "created_at": event.created_at,
        "actor": {
            "id": actor.id,
            "name": actor.name,
            "email": actor.email,
        }
        if actor
        else None,
    }


async def list_events(
    db: AsyncSession,
    project_id: int,
    user: User,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List project activity.

    Internal users see internal + client events; clients see only client-visible
    events (same visibility rules as the underlying entities).
    """
    from sqlalchemy import select

    from src.models.user import User as UserModel

    stmt = select(ActivityEvent).where(ActivityEvent.project_id == project_id)

    if user.role != UserRole.architect:
        stmt = stmt.where(ActivityEvent.visibility == "client")

    if event_type:
        stmt = stmt.where(ActivityEvent.event_type == event_type)

    stmt = stmt.order_by(ActivityEvent.created_at.desc()).limit(min(limit, 500))

    result = await db.execute(stmt)
    events = list(result.scalars().all())

    actor_ids = {e.actor_id for e in events}
    actors: dict[int, User] = {}
    if actor_ids:
        actor_result = await db.execute(select(UserModel).where(UserModel.id.in_(actor_ids)))
        actors = {u.id: u for u in actor_result.scalars().all()}

    return [_serialize_event(e, actors.get(e.actor_id)) for e in events]


async def ensure_activity_access(
    db: AsyncSession,
    project_id: int,
    user: User,
) -> None:
    """Verify the user can view the project's activity timeline (404 for others).

    Handles anonymous ClientSessions (scoped to exactly one project) and the
    admin superuser; delegates to the shared project access gate otherwise.
    """
    from src.api.dependencies import ClientSession
    from src.models.project import Project, ProjectMember

    if isinstance(user, ClientSession):
        from src.services.project import _get_project_with_access

        await _get_project_with_access(db, project_id, user)
        return
    if user.role == UserRole.admin:
        result = await db.execute(select(Project).where(Project.id == project_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == user.id:
        return
    if user.role == UserRole.architect and project.firm_id and user.firm_id == project.firm_id:
        return

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
