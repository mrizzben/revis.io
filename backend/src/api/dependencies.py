"""FastAPI dependency injection for authentication and authorization."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import decode_token
from src.models.project import Project
from src.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)

# Type aliases for cleaner dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)]


class ClientSession:
    """Anonymous client reviewer session granted via secure link + password.

    No sign-up is required: the owner/admin shares a secure link and password;
    the client enters the password on the link page and receives a JWT carrying
    a ``client_project_id`` claim. This wrapper behaves like a client ``User``
    (same ``role``/``id``/``name``/... attributes) but is scoped to exactly one
    project. The wrapped ``id`` is a per-project guest identity used as the
    author of comments/reviews.
    """

    def __init__(self, user: User, project_id: int) -> None:
        self.id = user.id
        self.role = user.role
        self.name = user.name
        self.email = user.email
        self.firm_id = user.firm_id
        self.is_firm_admin = user.is_firm_admin
        self.is_verified = user.is_verified
        self.is_active = user.is_active
        self.client_project_id = project_id


def is_architect_role(role: UserRole) -> bool:
    """Admin is a superuser: passes every architect-gated check."""
    return role in (UserRole.admin, UserRole.architect)



async def get_token_payload(
    credentials: BearerToken,
) -> dict:
    """Extract and validate JWT token from Bearer auth header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def _load_user(
    db: DBSession,
    payload: dict,
) -> User:
    """Load the active user referenced by a JWT payload's ``sub`` claim."""
    from src.models.user import User

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed subject",
        ) from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_current_user(
    db: DBSession,
    payload: dict = Depends(get_token_payload),
):
    """Get the current authenticated user from the JWT token.

    Returns the SQLAlchemy User model instance.
    """
    return await _load_user(db, payload)


async def get_current_participant(
    db: DBSession,
    payload: dict = Depends(get_token_payload),
):
    """Get the current actor: a registered User, or an anonymous client
    session scoped to one project (secure link + password, no sign-up).

    Client-visible endpoints use this so anonymous reviewers can view,
    comment and approve designs without creating an account.
    """
    user = await _load_user(db, payload)
    client_project_id = payload.get("client_project_id")
    if client_project_id is not None:
        if user.role != UserRole.client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client session",
            )
        try:
            client_project_id = int(client_project_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client session",
            )
        return ClientSession(user, client_project_id)
    return user


def require_role(*allowed_roles: str):
    """Dependency factory: require the current user to have one of the specified roles.

    Usage:
        @router.get("/admin")
        async def admin_route(user = Depends(require_role("architect"))):
            ...
    """

    async def role_checker(
        current_user=Depends(get_current_user),
    ):
        # Admin is the app superuser: passes every role requirement.
        if current_user.role == UserRole.admin or current_user.role in allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {', '.join(allowed_roles)}",
        )

    return role_checker


# Common dependency aliases
RequireArchitect = Annotated[None, Depends(require_role("architect"))]


async def get_project_for_internal(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Resolve a project and verify the user has internal (owner|collaborator|admin) access.

    Returns the project; raises 404 for non-internal users (incl. clients) to avoid
    disclosing internal content to external parties.
    """
    from sqlalchemy import select

    from src.models.project import Project, ProjectMember

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == current_user.id or current_user.role == UserRole.admin:
        return project

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None or member.role != "collaborator":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return project


async def get_project_for_owner(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Resolve a project and verify the user may act as its owner (full internal
    control): the project owner or an app admin. Collaborators receive 403
    (owner-only action); non-internal users (incl. clients) receive 404.
    """
    from sqlalchemy import select

    from src.models.project import Project, ProjectMember

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == current_user.id or current_user.role == UserRole.admin:
        return project

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member is None or member.role != "collaborator":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the project owner can perform this action",
    )


# Type aliases for internal-access dependencies
RequireProjectOwner = Annotated[Project, Depends(get_project_for_owner)]
RequireInternalProject = Annotated[Project, Depends(get_project_for_internal)]
Participant = Annotated[User | ClientSession, Depends(get_current_participant)]
