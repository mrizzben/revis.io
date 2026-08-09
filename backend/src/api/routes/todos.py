"""To-do API routes (internal team only)."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_user, get_project_for_internal
from src.models.project import Project
from src.models.user import User
from src.schemas.todo import TodoCreate, TodoResponse, TodoUpdate
from src.services.todo import create_todo, delete_todo, list_todos, update_todo

router = APIRouter(prefix="/projects/{project_id}/todos", tags=["To-Dos"])


@router.get("", response_model=list[TodoResponse])
async def get_todos(
    project_id: int,
    db: DBSession,
    project: Project = Depends(get_project_for_internal),
):
    return await list_todos(db, project_id)


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def post_todo(
    project_id: int,
    data: TodoCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_internal),
):
    return await create_todo(
        db, project, current_user, data.title, data.description, data.assignee_id
    )


@router.patch("/{todo_id}", response_model=TodoResponse)
async def patch_todo(
    project_id: int,
    todo_id: int,
    data: TodoUpdate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_internal),
):
    return await update_todo(
        db,
        project_id,
        todo_id,
        current_user,
        data.title,
        data.description,
        data.status,
        data.assignee_id,
    )


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_todo(
    project_id: int,
    todo_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project_for_internal),
):
    await delete_todo(db, project_id, todo_id)
