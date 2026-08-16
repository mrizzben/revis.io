"""Comment API routes."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_participant
from src.models.user import User
from src.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from src.services.comment import CommentService

router = APIRouter(tags=["Comments"])


@router.get(
    "/files/{file_id}/comments",
    response_model=list[CommentResponse],
)
async def list_comments(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_participant),
):
    from src.services import file as file_service
    from src.services import project as project_service

    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)
    return await CommentService.list_comments(db, file_id)


@router.post(
    "/files/{file_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    file_id: str,
    data: CommentCreate,
    db: DBSession,
    current_user: User = Depends(get_current_participant),
):
    return await CommentService.create_comment(db, file_id, data, current_user)


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
)
async def update_comment(
    comment_id: int,
    data: CommentUpdate,
    db: DBSession,
    current_user: User = Depends(get_current_participant),
):
    return await CommentService.update_comment(db, comment_id, data, current_user.id)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    comment_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_participant),
):
    await CommentService.delete_comment(db, comment_id, current_user.id)