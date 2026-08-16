"""Project, Firm, and Invitation services."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import ClientSession
from src.core.config import settings
from src.core.security import create_url_safe_token, hash_password, verify_password
from src.models.file import DesignFile, FileVersion
from src.models.milestone import Milestone
from src.models.project import Invitation, Project, ProjectMember
from src.models.user import Firm, User, UserRole
from src.services import file as file_service
from src.services.notification import send_invitation_email

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# Project Service (T027)
# ═══════════════════════════════════════════════════════════


async def create_project(
    db: AsyncSession,
    user: User,
    name: str,
    description: str | None = None,
    firm_id: int | None = None,
) -> Project:
    """Create a new project (architect or admin)."""
    if user.role not in (UserRole.architect, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only architects can create projects",
        )

    # Validate firm ownership
    if firm_id is not None and user.firm_id != firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create projects for your own firm",
        )

    project = Project(
        name=name.strip(),
        description=description.strip() if description else None,
        owner_id=user.id,
        firm_id=firm_id or user.firm_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    logger.info(
        "Project created",
        extra={
            "project_id": project.id,
            "owner_id": user.id,
            "firm_id": project.firm_id,
        },
    )
    return project


async def list_projects(
    db: AsyncSession,
    user: User,
    include_archived: bool = False,
) -> list[dict]:
    """List projects for the current user based on their role."""
    client_project_id = getattr(user, "client_project_id", None)
    if client_project_id is not None:
        # Anonymous client session (secure link): only the scoped project,
        # and only while client access remains enabled.
        result = await db.execute(
            select(Project).where(
                Project.id == client_project_id,
                Project.is_archived == include_archived,
                Project.client_token.is_not(None),
            )
        )
        projects = list(result.scalars().all())
    elif user.role == UserRole.admin:
        # Admin is the app superuser: sees every project.
        result = await db.execute(select(Project).where(Project.is_archived == include_archived))
        projects = list(result.scalars().all())
    elif user.role == UserRole.architect:
        # Architects see projects they own or firm projects
        query = select(Project).where(
            Project.owner_id == user.id,
            Project.is_archived == include_archived,
        )
        if user.firm_id:
            firm_query = select(Project).where(
                Project.firm_id == user.firm_id,
                Project.owner_id != user.id,
                Project.is_archived == include_archived,
            )
            projects = (await db.execute(query)).scalars().all()
            firm_projects = (await db.execute(firm_query)).scalars().all()
            projects = list(projects) + list(firm_projects)
        else:
            projects = (await db.execute(query)).scalars().all()
    else:
        # Clients see only projects they're members of
        query = (
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                ProjectMember.user_id == user.id,
                Project.is_archived == include_archived,
            )
        )
        projects = (await db.execute(query)).scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "owner_id": p.owner_id,
            "firm_id": p.firm_id,
            "is_archived": p.is_archived,
            "file_count": await _count_files(db, p.id),
            "milestone_count": await _count_milestones(db, p.id),
            "completed_milestone_count": await _count_completed_milestones(db, p.id),
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in projects
    ]


async def get_project(
    db: AsyncSession,
    project_id: int,
    user: User,
) -> Project:
    """Get a project by ID with access control."""
    project = await _get_project_with_access(db, project_id, user)
    return project


async def update_project(
    db: AsyncSession,
    project_id: int,
    user: User,
    name: str | None = None,
    description: str | None = None,
    is_archived: bool | None = None,
) -> Project:
    """Update a project (architect owner only)."""
    project = await _get_project_with_access(db, project_id, user, require_owner=True)

    if name is not None:
        project.name = name.strip()
    if description is not None:
        project.description = description.strip() if description else None
    if is_archived is not None:
        project.is_archived = is_archived

    project.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession,
    project_id: int,
    user: User,
    archive_only: bool = True,
    confirmation: str | None = None,
) -> None:
    """Archive or permanently delete a project (architect owner only).

    Archive keeps every object in RustFS (reversible via ``is_archived``).
    Permanent deletion removes the project rows AND the underlying objects
    (revisions, thumbnails, previews) from RustFS — irreversible.
    """
    project = await _get_project_with_access(db, project_id, user, require_owner=True)

    if archive_only:
        project.is_archived = True
        project.updated_at = datetime.now(UTC)
        await db.commit()
        logger.info("Project archived", extra={"project_id": project_id})
        return

    # Permanent deletion is a danger-zone action: the caller must type the
    # project name to confirm.
    if confirmation is None or confirmation.strip() != project.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation does not match the project name",
        )

    # Collect every object key owned by this project before the rows vanish.
    result = await db.execute(
        select(DesignFile)
        .options(selectinload(DesignFile.versions))
        .where(DesignFile.project_id == project_id)
    )
    files = list(result.scalars().all())

    s3 = file_service._get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    keys: set[str] = set()
    for f in files:
        keys.update(
            k
            for k in (f.s3_key, f.thumbnail_small_key, f.thumbnail_medium_key, f.preview_glb_key)
            if k
        )
        keys.update(v.s3_key for v in f.versions)

    # Remove the rows first (DB-level CASCADE). Deleting the design files
    # through the ORM cascades their loaded version rows so the dedup check
    # below is accurate in every environment (SQLite tests don't enforce FK
    # cascade). If an object delete fails the orphan stays in RustFS and is
    # reclaimed by storage maintenance — the reverse order would strand rows
    # pointing at deleted objects.
    for f in files:
        await db.delete(f)
    await db.flush()
    await db.delete(project)
    await db.flush()
    for key in keys:
        remaining = await db.execute(
            select(func.count()).select_from(FileVersion).where(FileVersion.s3_key == key)
        )
        if (remaining.scalar() or 0) > 0:
            continue  # deduplicated content still referenced elsewhere
        try:
            s3.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            # ponytail: log-and-continue like purge_soft_deleted; orphans are
            # reclaimed by maintenance. A full rollback would need staging.
            logger.error("Project delete: S3 delete failed", extra={"key": key, "error": str(e)})
    await db.commit()
    logger.info(
        "Project permanently deleted",
        extra={"project_id": project_id, "objects_removed": len(keys)},
    )


async def _get_project_with_access(
    db: AsyncSession,
    project_id: int,
    user: User | ClientSession,
    require_owner: bool = False,
) -> Project:
    """Get a project and verify the user has access.

    ``user`` may be a registered User (owner/architect/collaborator/client
    member) or an anonymous ClientSession scoped to one project via the
    client secure link.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    client_project_id = getattr(user, "client_project_id", None)

    if require_owner and project.owner_id != user.id and user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can perform this action",
        )

    if user.role == UserRole.client:
        if client_project_id is not None:
            # Anonymous client session: scoped to exactly this project, and
            # only while the owner/admin has client access enabled.
            if client_project_id != project_id or project.client_token is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
                )
        else:
            member_result = await db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user.id,
                )
            )
            if not member_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
                )

    return project


async def _count_files(db: AsyncSession, project_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(DesignFile)
        .where(
            DesignFile.project_id == project_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    return result.scalar() or 0


async def _count_milestones(db: AsyncSession, project_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
        )
    )
    return result.scalar() or 0


async def _count_completed_milestones(db: AsyncSession, project_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
            Milestone.is_completed.is_(True),
        )
    )
    return result.scalar() or 0


# ═══════════════════════════════════════════════════════════
# Invitation Service (T029)
# ═══════════════════════════════════════════════════════════


async def create_invitation(
    db: AsyncSession,
    project_id: int,
    email: str,
    invited_by: User,
) -> Invitation:
    """Create an invitation for a client to join a project."""
    project = await _get_project_with_access(db, project_id, invited_by, require_owner=True)

    if invited_by.role not in (UserRole.architect, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only architects can invite clients",
        )

    # Check if the email is already a member
    user_result = await db.execute(select(User).where(User.email == email))
    existing_user = user_result.scalar_one_or_none()
    if existing_user:
        member_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == existing_user.id,
            )
        )
        if member_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This user is already a member of the project",
            )

    # Resend: delete any existing unused invitation for this email+project
    existing_invites = await db.execute(
        select(Invitation).where(
            Invitation.email == email,
            Invitation.project_id == project_id,
            Invitation.is_used.is_(False),
        )
    )
    for inv in existing_invites.scalars().all():
        await db.delete(inv)

    token = create_url_safe_token()
    invitation = Invitation(
        email=email,
        token=token,
        project_id=project_id,
        invited_by_id=invited_by.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    send_invitation_email(
        to_email=email,
        project_name=project.name,
        invited_by_name=invited_by.name,
        token=token,
    )

    return invitation


async def get_invitation(
    db: AsyncSession,
    token: str,
) -> dict:
    """Get invitation details (public endpoint, no auth needed)."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()

    if not invitation or invitation.is_used:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation has expired")

    # Get project and inviter names
    proj_result = await db.execute(select(Project).where(Project.id == invitation.project_id))
    project = proj_result.scalar_one_or_none()

    user_result = await db.execute(select(User).where(User.id == invitation.invited_by_id))
    inviter = user_result.scalar_one_or_none()

    return {
        "email": invitation.email,
        "project_name": project.name if project else "Unknown Project",
        "invited_by_name": inviter.name if inviter else "Unknown",
    }


# ═══════════════════════════════════════════════════════════
# Client Secure-Link Access (no sign-up required)
# ═══════════════════════════════════════════════════════════

GUEST_EMAIL_DOMAIN = "revis.io"


def _guest_email(project_id: int) -> str:
    return f"guest-{project_id}@{GUEST_EMAIL_DOMAIN}"


async def ensure_project_guest_user(db: AsyncSession, project: Project) -> User:
    """Per-project guest identity for anonymous client sessions.

    The owner/admin enables client access; clients who use the secure link
    (no sign-up) act through this identity so comments/reviews have a stable
    author. Emails on the reserved ``guest-*@revis.io`` namespace cannot be
    registered by real users (see ``register_user``).
    """
    result = await db.execute(select(User).where(User.email == _guest_email(project.id)))
    guest = result.scalar_one_or_none()
    if guest is not None:
        return guest

    guest = User(
        email=_guest_email(project.id),
        name="Client Guest",
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        role=UserRole.client,
        is_active=True,
        is_verified=True,
    )
    db.add(guest)
    await db.flush()
    return guest


async def configure_client_access(
    db: AsyncSession,
    project: Project,
    password: str | None = None,
) -> Project:
    """Enable or rotate a project's client secure-link access.

    Sets (or replaces) the client access password and generates a fresh link
    token. Called by the project owner or an admin. Re-running rotates the
    token and invalidates previously shared links/sessions.
    """
    if password is not None:
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client access password must be at least 8 characters",
            )
        project.client_password_hash = hash_password(password)
    elif project.client_password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A client access password is required the first time",
        )

    project.client_token = create_url_safe_token()
    await db.commit()
    await db.refresh(project)
    await ensure_project_guest_user(db, project)
    await db.commit()
    return project


async def disable_client_access(db: AsyncSession, project: Project) -> Project:
    """Disable the project's client secure-link access.

    Clears the link token and password; existing client sessions for this
    project are rejected on their next request.
    """
    project.client_token = None
    project.client_password_hash = None
    await db.commit()
    await db.refresh(project)
    return project


async def get_client_access_info(db: AsyncSession, token: str) -> dict:
    """Public info for the secure-link landing page (no auth required)."""
    result = await db.execute(select(Project).where(Project.client_token == token))
    project = result.scalar_one_or_none()
    if not project or project.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return {
        "project_name": project.name,
        "archived": project.is_archived,
    }


async def authenticate_client_access(
    db: AsyncSession,
    token: str,
    password: str,
) -> tuple[Project, User]:
    """Validate a client's secure-link password; returns the project and the
    per-project guest identity for the resulting scoped session.
    """
    result = await db.execute(select(Project).where(Project.client_token == token))
    project = result.scalar_one_or_none()
    if not project or project.client_password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid link or password"
        )
    if project.is_archived:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project is archived")
    if not verify_password(password, project.client_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid link or password"
        )
    guest = await ensure_project_guest_user(db, project)
    await db.commit()
    return project, guest


# ═══════════════════════════════════════════════════════════
# Firm Service (T030)
# ═══════════════════════════════════════════════════════════


async def create_firm(
    db: AsyncSession,
    user: User,
    name: str,
) -> Firm:
    """Create a new firm. The creating user becomes the firm admin."""
    if user.role not in (UserRole.architect, UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only architects can create firms",
        )

    if user.firm_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already belong to a firm",
        )

    firm = Firm(name=name.strip())
    db.add(firm)
    await db.commit()
    await db.refresh(firm)

    # Set user as firm admin
    user.firm_id = firm.id
    user.is_firm_admin = True
    await db.commit()
    await db.refresh(firm)

    return firm


async def list_firms(
    db: AsyncSession,
    user: User,
) -> list[dict]:
    """List firms (firm admins see their firm)."""
    if user.firm_id is None:
        return []

    result = await db.execute(select(Firm).where(Firm.id == user.firm_id))
    firms = result.scalars().all()

    output = []
    for f in firms:
        member_count = await db.execute(
            select(func.count()).select_from(User).where(User.firm_id == f.id)
        )
        output.append(
            {
                "id": f.id,
                "name": f.name,
                "member_count": member_count.scalar() or 0,
                "created_at": f.created_at,
            }
        )

    return output


async def get_firm_members(
    db: AsyncSession,
    firm_id: int,
    user: User,
) -> list[User]:
    """List members of a firm (firm admin only)."""
    if user.firm_id != firm_id or not user.is_firm_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only firm admins can view member list",
        )

    result = await db.execute(select(User).where(User.firm_id == firm_id, User.is_active.is_(True)))
    return list(result.scalars().all())


async def add_firm_member(
    db: AsyncSession,
    firm_id: int,
    email: str,
    user: User,
) -> User:
    """Add an architect to a firm (firm admin only)."""
    if user.firm_id != firm_id or not user.is_firm_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only firm admins can add members",
        )

    result = await db.execute(select(User).where(User.email == email))
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if member.role != UserRole.architect:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only architects can be added to a firm",
        )

    if member.firm_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to a firm",
        )

    member.firm_id = firm_id
    await db.commit()
    await db.refresh(member)
    return member
