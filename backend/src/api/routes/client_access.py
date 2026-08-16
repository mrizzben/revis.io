"""Client secure-link access routes.

Clients are reviewer-only: view, comment/review, approve designs. Access is
granted per project through a secure link + password set by the project owner
or an admin — no sign-up required (sign-up remains available for clients who
want a persistent account). Routes: setup/rotate/disable (owner|admin),
public link info, and password-based session authentication.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.api.dependencies import DBSession, get_project_for_owner
from src.core.config import settings
from src.core.security import create_access_token
from src.models.project import Project
from src.services import project as project_service

router = APIRouter(tags=["Client Access"])


class ClientAccessSetup(BaseModel):
    """Set (or rotate) the client access password for a project."""

    password: str | None = None


class ClientAccessAuth(BaseModel):
    """Authenticate on the secure link with the owner/admin-provided password."""

    token: str
    password: str


@router.get("/client-access/{token}")
async def get_client_access_info(
    token: str,
    db: DBSession,
):
    """Public landing info for the secure link (no auth required)."""
    return await project_service.get_client_access_info(db, token)


@router.post("/client-access/authenticate")
async def authenticate_client_access(
    data: ClientAccessAuth,
    db: DBSession,
):
    """Exchange the secure-link password for a scoped client session token.

    The resulting JWT carries ``client_project_id``: it only grants access to
    that one project (view, comment, review, approve) until it expires.
    """
    project, guest = await project_service.authenticate_client_access(
        db, data.token, data.password
    )
    access_token = create_access_token(
        subject=guest.id,
        role="client",
        client_project_id=project.id,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "project_id": project.id,
        "project_name": project.name,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/projects/{project_id}/client-access")
async def configure_client_access(
    project_id: int,
    data: ClientAccessSetup,
    db: DBSession,
    project: Project = Depends(get_project_for_owner),
):
    """Enable or rotate client secure-link access (project owner or admin only).

    Sets/replaces the client password and generates a fresh secure link.
    """
    project = await project_service.configure_client_access(db, project, data.password)
    return {
        "token": project.client_token,
        "url": f"{settings.FRONTEND_URL}/client-access/{project.client_token}",
        "password_set": project.client_password_hash is not None,
    }


@router.delete("/projects/{project_id}/client-access", status_code=status.HTTP_204_NO_CONTENT)
async def disable_client_access(
    project_id: int,
    db: DBSession,
    project: Project = Depends(get_project_for_owner),
):
    """Disable client secure-link access (project owner or admin only)."""
    await project_service.disable_client_access(db, project)
