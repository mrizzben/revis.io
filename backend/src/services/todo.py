"""To-do service: CRUD, assignment, status changes with notification fan-out."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification import NotificationType
from src.models.project import Project
from src.models.todo import ToDo
from src.models.user import User
from src.services.notification import create_notification
from src.websocket import get_manager

VALID_STATUSES = {"open", "complete"}


async def list_todos(db: AsyncSession, project_id: int) -> list[dict]:
    """List a project's to-dos. Caller must have internal access (route dependency)."""
    result = await db.execute(
        select(ToDo).where(ToDo.project_id == project_id).order_by(ToDo.created_at.desc())
    )
    todos = result.scalars().all()
    output = []
    for t in todos:
        output.append(await _todo_to_dict_from_db(db, t))
    return output


async def _todo_to_dict_from_db(db: AsyncSession, todo: ToDo) -> dict:
    assignee = await db.get(User, todo.assignee_id) if todo.assignee_id else None
    creator = await db.get(User, todo.created_by)
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "status": todo.status,
        "assignee": {"id": assignee.id, "name": assignee.name} if assignee else None,
        "created_by": {"id": creator.id, "name": creator.name} if creator else None,
        "created_at": todo.created_at,
        "updated_at": todo.updated_at,
    }


async def create_todo(
    db: AsyncSession,
    project: Project,
    created_by: User,
    title: str,
    description: str | None = None,
    assignee_id: int | None = None,
) -> dict:
    """Create a to-do; notify assignee when assigned (internal access guaranteed)."""
    await _validate_assignee(db, project, assignee_id)

    todo = ToDo(
        project_id=project.id,
        created_by=created_by.id,
        assignee_id=assignee_id,
        title=title.strip(),
        description=description.strip() if description else None,
        status="open",
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)

    if assignee_id and assignee_id != created_by.id:
        assignee = await db.get(User, assignee_id)
        await create_notification(
            db,
            user_id=assignee_id,
            ntype=NotificationType.todo_assigned,
            title=f"To-do assigned in {project.name}",
            body=f"'{todo.title}' was assigned to you",
            reference_id=todo.id,
        )

    await _broadcast(db, project, "todo_added", todo.id)
    return await _todo_to_dict_from_db(db, todo)


async def update_todo(
    db: AsyncSession,
    project_id: int,
    todo_id: int,
    actor: User,
    title: str | None = None,
    description: str | None = None,
    status_value: str | None = None,
    assignee_id: int | None = None,
) -> dict:
    """Update a to-do (any internal team member). Notify assignee on assignment change."""
    todo = await _get_todo(db, project_id, todo_id)
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()

    if status_value is not None:
        if status_value not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'open' or 'complete'",
            )
        todo.status = status_value

    if title is not None and title.strip():
        todo.title = title.strip()
    if description is not None:
        todo.description = description.strip() if description else None

    if assignee_id is not None:
        await _validate_assignee(db, project, assignee_id)
        if assignee_id != todo.assignee_id:
            todo.assignee_id = assignee_id
            if assignee_id != actor.id:
                assignee = await db.get(User, assignee_id)
                await create_notification(
                    db,
                    user_id=assignee_id,
                    ntype=NotificationType.todo_assigned,
                    title=f"To-do assigned in {project.name}",
                    body=f"'{todo.title}' was assigned to you",
                    reference_id=todo.id,
                )

    await db.commit()
    await db.refresh(todo)
    await _broadcast(db, project, "todo_updated", todo.id)
    return await _todo_to_dict_from_db(db, todo)


async def delete_todo(db: AsyncSession, project_id: int, todo_id: int) -> None:
    """Delete a to-do (any internal team member)."""
    todo = await _get_todo(db, project_id, todo_id)
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
    await db.delete(todo)
    await db.commit()
    await _broadcast(db, project, "todo_deleted", todo_id)


async def _get_todo(db: AsyncSession, project_id: int, todo_id: int) -> ToDo:
    result = await db.execute(select(ToDo).where(ToDo.id == todo_id, ToDo.project_id == project_id))
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="To-do not found")
    return todo


async def _validate_assignee(db: AsyncSession, project: Project, assignee_id: int | None) -> None:
    """Assignee must be an internal-team member (owner or collaborator)."""
    if assignee_id is None:
        return
    from src.models.project import ProjectMember

    if assignee_id == project.owner_id:
        return
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == assignee_id,
            ProjectMember.role == "collaborator",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be an internal team member",
        )


async def _broadcast(db: AsyncSession, project: Project, event_type: str, todo_id: int) -> None:
    try:
        from src.services.collaboration import get_internal_team_ids

        ws = get_manager()
        await ws.broadcast_to_project_team(
            project.id,
            {
                "type": event_type,
                "project_id": project.id,
                "todo_id": todo_id,
            },
            await get_internal_team_ids(db, project),
        )
    except RuntimeError:
        pass
