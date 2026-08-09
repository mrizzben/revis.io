"""Collaborator API routes (internal team management)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.dependencies import (
    DBSession,
    get_current_user,
    get_project_for_internal,
    get_project_for_owner,
)
from src.models.project import Project
from src.models.user import User
from src.services.collaboration import (
    add_collaborator as add_collaborator_svc,
)
from src.services.collaboration import (
    list_collaborators as list_collaborators_svc,
)
from src.services.collaboration import (
    remove_collaborator as remove_collaborator_svc,
)

router = APIRouter(prefix="/projects/{project_id}/collaborators", tags=["Collaborators"])


class CollaboratorAdd(BaseModel):
    email: str | None = None
    user_id: int | None = None


@router.get("")
async def list_collaborators(
    project_id: int,
    db: DBSession,
    project: Project = Depends(get_project_for_internal),
):
    return await list_collaborators_svc(db, project_id, project)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_collaborator(
    project_id: int,
    data: CollaboratorAdd,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_owner),
):
    if data.email is None and data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'email' or 'user_id'",
        )
    return await add_collaborator_svc(
        db, project_id, project, current_user, data.email, data.user_id
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collaborator(
    project_id: int,
    user_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_owner),
):
    await remove_collaborator_svc(db, project_id, project, current_user, user_id)
