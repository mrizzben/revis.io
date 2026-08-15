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
from src.models.user import User

security_scheme = HTTPBearer(auto_error=False)

# Type aliases for cleaner dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)]


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
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user(
    db: DBSession,
    payload: dict = Depends(get_token_payload),
):
    """Get the current authenticated user from the JWT token.

    Returns the SQLAlchemy User model instance.
    """
    from src.models.user import User

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

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
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


# Common dependency aliases
RequireArchitect = Annotated[None, Depends(require_role("architect"))]


async def get_project_for_internal(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Resolve a project and verify the user has internal (owner|collaborator) access.

    Returns the project; raises 404 for non-internal users (incl. clients) to avoid
    disclosing internal content to external parties.
    """
    from sqlalchemy import select

    from src.models.project import Project, ProjectMember

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == current_user.id:
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
    """Resolve a project and verify the user is its owner (full internal control).

    Non-internal users (incl. clients) receive 404 to avoid disclosing the
    project; internal collaborators receive 403 (owner-only action).
    """
    from sqlalchemy import select

    from src.models.project import Project, ProjectMember

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.owner_id == current_user.id:
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
