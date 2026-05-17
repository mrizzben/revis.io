"""Invitation routes: public lookup."""

from fastapi import APIRouter, Depends

from src.api.dependencies import DBSession
from src.services import project as project_service

router = APIRouter(prefix="/invitations", tags=["Invitations"])


@router.get("/{token}")
async def get_invitation(
    token: str,
    db: DBSession,
):
    """View invitation details (public, before registration)."""
    return await project_service.get_invitation(db, token)
