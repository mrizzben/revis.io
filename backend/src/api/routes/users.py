"""User routes: profile."""

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_participant
from src.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_participant),
):
    """Get current user profile.

    Anonymous client sessions (secure link) also expose ``client_project_id``
    so the frontend can scope the UI to the single granted project.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
        "firm_id": current_user.firm_id,
        "is_firm_admin": current_user.is_firm_admin,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "client_project_id": getattr(current_user, "client_project_id", None),
    }
