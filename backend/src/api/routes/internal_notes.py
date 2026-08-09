"""Internal note API routes (internal team only)."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_user, get_project_for_internal
from src.models.project import Project
from src.models.user import User
from src.schemas.internal_note import (
    InternalNoteCreate,
    InternalNoteReplyCreate,
)
from src.services.internal_note import create_note, create_reply, list_notes

router = APIRouter(prefix="/projects/{project_id}/internal-notes", tags=["Internal Notes"])


@router.get("")
async def get_notes(
    project_id: int,
    db: DBSession,
    project: Project = Depends(get_project_for_internal),
):
    return {"notes": await list_notes(db, project_id)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_note(
    project_id: int,
    data: InternalNoteCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_internal),
):
    return await create_note(db, project, current_user, data.body, data.mentions)


@router.post("/{note_id}/replies", status_code=status.HTTP_201_CREATED)
async def post_reply(
    project_id: int,
    note_id: int,
    data: InternalNoteReplyCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_internal),
):
    return await create_reply(db, project_id, note_id, current_user.id, data.body)
