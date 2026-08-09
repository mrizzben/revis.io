"""Internal note service: CRUD, threaded replies, and @mention fan-out."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.internal_note import InternalNote, Mention
from src.models.notification import NotificationType
from src.models.project import Project
from src.models.user import User
from src.services.collaboration import get_internal_team_ids
from src.services.notification import create_notification
from src.websocket import get_manager


def _note_to_dict(note: InternalNote) -> dict:
    """Serialize a note with replies nested and author/mention info."""
    return {
        "id": note.id,
        "author": ({"id": note.author.id, "name": note.author.name} if note.author else None),
        "body": note.body,
        "mentions": [
            {"user_id": m.user_id, "name": m.user.name if m.user else ""} for m in note.mentions
        ],
        "replies": [
            {
                "id": r.id,
                "author": {"id": r.author.id, "name": r.author.name} if r.author else None,
                "body": r.body,
                "parent_id": r.parent_id,
                "created_at": r.created_at,
            }
            for r in note.replies
        ],
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def list_notes(db: AsyncSession, project_id: int) -> list[dict]:
    """List top-level internal notes (with replies) for an internal project.

    Caller must have internal access (checked by route dependency).
    """
    result = await db.execute(
        select(InternalNote)
        .options(
            selectinload(InternalNote.author),
            selectinload(InternalNote.replies).selectinload(InternalNote.author),
            selectinload(InternalNote.mentions).selectinload(Mention.user),
        )
        .where(InternalNote.project_id == project_id, InternalNote.parent_id.is_(None))
        .order_by(InternalNote.created_at.desc())
    )
    notes = result.scalars().all()
    return [_note_to_dict(n) for n in notes]


async def _get_note(db: AsyncSession, note_id: int) -> InternalNote:
    result = await db.execute(
        select(InternalNote)
        .options(
            selectinload(InternalNote.author),
            selectinload(InternalNote.mentions).selectinload(Mention.user),
        )
        .where(InternalNote.id == note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


async def _notify_mentions(
    db: AsyncSession,
    note: InternalNote,
    project: Project,
    mentioned_ids: list[int],
) -> None:
    """Create Mention rows and fan out in-app notifications.

    Only existing internal-team members (owner or collaborator) can be mentioned;
    unknowns are skipped. Excludes the author.
    """
    from src.models.project import ProjectMember

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.role == "collaborator",
        )
    )
    valid_ids = {m.user_id for m in result.scalars().all()} | {project.owner_id}

    seen: set[int] = set()
    for user_id in mentioned_ids:
        if user_id not in valid_ids:
            continue
        if user_id == note.author_id or user_id in seen:
            continue
        seen.add(user_id)
        db.add(Mention(note_id=note.id, user_id=user_id, notified=True))
        await create_notification(
            db,
            user_id=user_id,
            ntype=NotificationType.mention,
            title=f"You were mentioned in {project.name}",
            body=note.body[:200],
            reference_id=note.id,
        )


async def create_note(
    db: AsyncSession,
    project: Project,
    author: User,
    body: str,
    mentioned_ids: list[int] | None = None,
) -> dict:
    """Create a top-level internal note and fan out mentions."""
    note = InternalNote(project_id=project.id, author_id=author.id, body=body.strip())
    db.add(note)
    await db.commit()
    await db.refresh(note)

    if mentioned_ids:
        await _notify_mentions(db, note, project, mentioned_ids)
        await db.commit()

    try:
        ws = get_manager()
        await ws.broadcast_to_project_team(
            project.id,
            {
                "type": "internal_note_added",
                "project_id": project.id,
                "note_id": note.id,
            },
            await get_internal_team_ids(db, project),
        )
    except RuntimeError:
        pass

    return await _serialize_with_children(db, note)


async def _serialize_with_children(db: AsyncSession, note: InternalNote) -> dict:
    """Re-query a note with replies/mentions loaded for a full response."""
    result = await db.execute(
        select(InternalNote)
        .options(
            selectinload(InternalNote.author),
            selectinload(InternalNote.replies).selectinload(InternalNote.author),
            selectinload(InternalNote.mentions).selectinload(Mention.user),
        )
        .where(InternalNote.id == note.id)
    )
    loaded = result.scalar_one()
    return _note_to_dict(loaded)


async def create_reply(
    db: AsyncSession,
    project_id: int,
    note_id: int,
    author_id: int,
    body: str,
) -> dict:
    """Create a reply to a top-level note (internal access guaranteed by route)."""
    note = await _get_note(db, note_id)
    if note.project_id != project_id or note.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent note not found in this project",
        )

    reply = InternalNote(
        project_id=project_id,
        author_id=author_id,
        parent_id=note_id,
        body=body.strip(),
    )
    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    try:
        ws = get_manager()
        await ws.broadcast_to_project_team(
            project_id,
            {
                "type": "internal_note_added",
                "project_id": project_id,
                "note_id": note_id,
                "parent_id": reply.id,
            },
            await get_internal_team_ids(db, project),
        )
    except RuntimeError:
        pass

    return {
        "id": reply.id,
        "author": {"id": author_id, "name": ""},
        "body": reply.body,
        "parent_id": reply.parent_id,
        "created_at": reply.created_at,
    }
