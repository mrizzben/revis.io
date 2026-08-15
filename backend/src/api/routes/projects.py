"""Project routes: CRUD, invitations, files listing, and polling fallback."""

from datetime import UTC

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import DBSession, get_current_user, require_role
from src.models.file import DesignFile
from src.models.milestone import Milestone
from src.models.user import User, UserRole
from src.schemas.project import (
    InviteClientRequest,
    ProjectCreate,
    ProjectUpdate,
)
from src.services import file as file_service
from src.services import project as project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("")
async def list_projects(
    db: DBSession,
    current_user: User = Depends(get_current_user),
    archived: bool = Query(False),
):
    """List current user's projects."""
    return await project_service.list_projects(db, current_user, include_archived=archived)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Create a new project (architect only)."""
    project = await project_service.create_project(
        db=db,
        user=current_user,
        name=request.name,
        description=request.description,
        firm_id=request.firm_id,
    )
    return project


@router.get("/{project_id}/files")
async def list_project_files(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    milestone_id: int | None = Query(None),
):
    """List project design items with revision visibility applied per role (T7).

    Clients only ever receive items that have an issued revision.
    """
    await project_service._get_project_with_access(db, project_id, current_user)

    query = (
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by), selectinload(DesignFile.design_option))
        .where(DesignFile.project_id == project_id, DesignFile.is_deleted.is_(False))
    )
    if milestone_id is not None:
        query = query.where(DesignFile.milestone_id == milestone_id)
    result = await db.execute(query)
    files = list(result.scalars().all())

    if current_user.role == UserRole.client:
        visible = []
        for f in files:
            versions = await file_service.list_client_versions(db, str(f.id))
            if versions:
                visible.append(f)
        return [await file_service.build_file_payload(db, f, current_user) for f in visible]

    return [await file_service.build_file_payload(db, f, current_user) for f in files]


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get project details including milestones and files."""
    project = await project_service.get_project(db, project_id, current_user)

    # Load related data
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.models.file import DesignFile

    # Get milestones
    milestone_result = await db.execute(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.position)
    )
    milestones = milestone_result.scalars().all()

    # Get files (role-aware payloads; clients see only issued items)
    file_result = await db.execute(
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by), selectinload(DesignFile.design_option))
        .where(DesignFile.project_id == project_id, DesignFile.is_deleted.is_(False))
        .order_by(DesignFile.created_at.desc())
    )
    files = file_result.scalars().all()

    if current_user.role == UserRole.client:
        visible_files = []
        for f in files:
            versions = await file_service.list_client_versions(db, str(f.id))
            if versions:
                visible_files.append(f)
        file_payloads = [
            await file_service.build_file_payload(db, f, current_user) for f in visible_files
        ]
    else:
        file_payloads = [await file_service.build_file_payload(db, f, current_user) for f in files]

    # Counts
    from sqlalchemy import func

    file_count = await db.execute(
        select(func.count())
        .select_from(DesignFile)
        .where(
            DesignFile.project_id == project_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    milestone_count_result = await db.execute(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
        )
    )
    completed_count = await db.execute(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
            Milestone.is_completed.is_(True),
        )
    )

    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "owner_id": project.owner_id,
        "firm_id": project.firm_id,
        "is_archived": project.is_archived,
        "file_count": len(file_payloads),
        "milestone_count": milestone_count_result.scalar() or 0,
        "completed_milestone_count": completed_count.scalar() or 0,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "milestones": [
            {
                "id": m.id,
                "project_id": m.project_id,
                "name": m.name,
                "description": m.description,
                "position": m.position,
                "is_completed": m.is_completed,
                "completed_at": m.completed_at,
                "file_count": 0,
                "created_at": m.created_at,
            }
            for m in milestones
        ],
        "files": file_payloads,
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Update a project (architect owner only)."""
    return await project_service.update_project(
        db=db,
        project_id=project_id,
        user=current_user,
        name=request.name,
        description=request.description,
        is_archived=request.is_archived,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
    archive_only: bool = Query(True),
):
    """Delete or archive a project (architect owner only)."""
    await project_service.delete_project(
        db=db,
        project_id=project_id,
        user=current_user,
        archive_only=archive_only,
    )
    if archive_only:
        from src.services import activity

        await activity.record_event(
            db,
            project_id=project_id,
            actor_id=current_user.id,
            event_type="project_archived",
            entity_type="project",
            entity_id=project_id,
            payload={},
            visibility="client",
        )


# ── Invitations ───────────────────────────────────────────


@router.post("/{project_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_client(
    project_id: int,
    request: InviteClientRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Invite a client to a project (architect only)."""
    invitation = await project_service.create_invitation(
        db=db,
        project_id=project_id,
        email=request.email,
        invited_by=current_user,
    )
    from src.services import activity

    await activity.record_event(
        db,
        project_id=project_id,
        actor_id=current_user.id,
        event_type="client_invited",
        entity_type="invitation",
        entity_id=invitation.id,
        payload={"email": request.email},
        visibility="client",
    )
    return {
        "id": invitation.id,
        "email": invitation.email,
        "token": invitation.token,
        "expires_at": invitation.expires_at,
        "is_used": invitation.is_used,
        "created_at": invitation.created_at,
    }


@router.get("/{project_id}/updates")
async def check_updates(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    since: str = Query(None, description="ISO 8601 timestamp"),
):
    """Polling fallback for WebSocket: check if project has updates since timestamp."""
    from datetime import datetime

    from sqlalchemy import func, select

    from src.models.file import DesignFile

    # Verify access
    await project_service._get_project_with_access(db, project_id, current_user)

    latest_file = await db.execute(
        select(func.max(DesignFile.updated_at)).where(
            DesignFile.project_id == project_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    latest_milestone = await db.execute(
        select(func.max(Milestone.updated_at)).where(
            Milestone.project_id == project_id,
        )
    )

    file_ts = latest_file.scalar()
    milestone_ts = latest_milestone.scalar()

    newest = file_ts
    if milestone_ts and (newest is None or milestone_ts > newest):
        newest = milestone_ts

    has_updates = False
    if since and newest:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            has_updates = newest > since_dt
        except (ValueError, AttributeError):
            has_updates = True

    return {
        "has_updates": has_updates,
        "timestamp": newest.isoformat() if newest else datetime.now(UTC).isoformat(),
    }
