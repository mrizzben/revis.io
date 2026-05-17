"""Milestone API routes."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_user, require_role
from src.models.user import User
from src.schemas.milestone import MilestoneCreate, MilestoneUpdate, MilestoneResponse
from src.services.milestone import MilestoneService

router = APIRouter(tags=["Milestones"])


@router.get(
    "/projects/{project_id}/milestones",
    response_model=list[MilestoneResponse],
)
async def list_milestones(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    return await MilestoneService.list_milestones(db, project_id)


@router.post(
    "/projects/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    project_id: int,
    data: MilestoneCreate,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    return await MilestoneService.create_milestone(
        db, project_id, data, current_user
    )


@router.patch(
    "/milestones/{milestone_id}",
    response_model=MilestoneResponse,
)
async def update_milestone(
    milestone_id: int,
    data: MilestoneUpdate,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    return await MilestoneService.update_milestone(
        db, milestone_id, data, current_user
    )


@router.delete(
    "/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    milestone_id: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    await MilestoneService.delete_milestone(db, milestone_id, current_user)