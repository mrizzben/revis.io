"""Internal collaboration service: internal-team access gate and collaborator management."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project, ProjectMember
from src.models.user import User


async def get_internal_project(
    db: AsyncSession,
    project_id: int,
    user: User,
) -> Project:
    """Get a project and verify the user has internal (owner|collaborator) access.

    Clients and non-members receive 404 to avoid disclosing project existence
    or internal content. This is THE gate for all internal collaboration APIs.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == user.id:
        return project

    member = await _get_membership(db, project_id, user.id)
    if member is None or member.role != "collaborator":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_membership(db: AsyncSession, project_id: int, user_id: int) -> ProjectMember | None:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_internal_team_ids(db: AsyncSession, project: Project) -> list[int]:
    """Return user ids of the internal team (owner + collaborators)."""
    result = await db.execute(
        select(ProjectMember.user_id).where(
            ProjectMember.project_id == project.id,
            ProjectMember.role == "collaborator",
        )
    )
    return [project.owner_id] + list(result.scalars().all())


async def list_collaborators(db: AsyncSession, project_id: int, project: Project) -> dict:
    """List the internal team (owner + collaborators). Requires internal access."""
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id, ProjectMember.role == "collaborator")
        .order_by(ProjectMember.joined_at)
    )
    members = result.scalars().all()

    collaborators = []
    for m in members:
        user = await db.get(User, m.user_id)
        if user is None:
            continue
        collaborators.append(
            {
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": m.role,
                "joined_at": m.joined_at,
            }
        )

    owner = await db.get(User, project.owner_id)
    return {
        "collaborators": collaborators,
        "owner": (
            {"user_id": owner.id, "email": owner.email, "name": owner.name} if owner else None
        ),
    }


async def add_collaborator(
    db: AsyncSession,
    project_id: int,
    project: Project,
    actor: User,
    email: str | None = None,
    user_id: int | None = None,
) -> dict:
    """Add a collaborator by email or user id. Owner-only (enforced by caller)."""
    target: User | None = None
    if user_id is not None:
        target = await db.get(User, user_id)
    elif email:
        result = await db.execute(select(User).where(User.email == email))
        target = result.scalar_one_or_none()

    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == project.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The project owner is already a member of the internal team",
        )
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already the owner of this project",
        )

    member = await _get_membership(db, project_id, target.id)
    if member is not None and member.role == "collaborator":
        # Idempotent add: already a collaborator
        return {
            "user_id": target.id,
            "email": target.email,
            "name": target.name,
            "role": member.role,
            "joined_at": member.joined_at,
        }

    if member is not None:
        # Existing client member is promoted to collaborator
        member.role = "collaborator"
        await db.commit()
        await db.refresh(member)
        return {
            "user_id": target.id,
            "email": target.email,
            "name": target.name,
            "role": member.role,
            "joined_at": member.joined_at,
        }

    new_member = ProjectMember(
        project_id=project_id,
        user_id=target.id,
        role="collaborator",
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)
    return {
        "user_id": target.id,
        "email": target.email,
        "name": target.name,
        "role": new_member.role,
        "joined_at": new_member.joined_at,
    }


async def remove_collaborator(
    db: AsyncSession,
    project_id: int,
    project: Project,
    actor: User,
    user_id: int,
) -> None:
    """Remove a collaborator (immediate access revocation). Owner-only (enforced by caller).

    Open to-dos assigned to the removed collaborator are reassigned to the
    project owner so work is not lost (spec edge case).
    """
    if user_id == project.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The project owner cannot be removed",
        )

    member = await _get_membership(db, project_id, user_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaborator not found")

    if member.role != "collaborator":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a collaborator on this project",
        )

    from src.models.todo import ToDo

    open_todos = await db.execute(
        select(ToDo).where(
            ToDo.project_id == project_id,
            ToDo.assignee_id == user_id,
            ToDo.status == "open",
        )
    )
    for todo in open_todos.scalars().all():
        todo.assignee_id = project.owner_id

    await db.delete(member)
    await db.commit()
