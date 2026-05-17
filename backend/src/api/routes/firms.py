"""Firm routes: create, list, manage members."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_user, require_role
from src.models.user import User
from src.schemas.user import AddFirmMemberRequest, CreateFirmRequest
from src.services import project as project_service

router = APIRouter(prefix="/firms", tags=["Firms"])


@router.get("")
async def list_firms(
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List firms (firm members see their firm)."""
    return await project_service.list_firms(db, current_user)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_firm(
    request: CreateFirmRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Create a new firm (becomes firm admin)."""
    firm = await project_service.create_firm(
        db=db,
        user=current_user,
        name=request.name,
    )

    return {
        "id": firm.id,
        "name": firm.name,
        "member_count": 1,
        "created_at": firm.created_at,
    }


@router.get("/{firm_id}/members")
async def get_firm_members(
    firm_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List firm members (firm admin only)."""
    members = await project_service.get_firm_members(db, firm_id, current_user)
    return [
        {
            "id": m.id,
            "email": m.email,
            "name": m.name,
            "role": m.role.value if hasattr(m.role, 'value') else m.role,
            "firm_id": m.firm_id,
            "is_firm_admin": m.is_firm_admin,
            "is_verified": m.is_verified,
            "created_at": m.created_at,
        }
        for m in members
    ]


@router.post("/{firm_id}/members")
async def add_firm_member(
    firm_id: int,
    request: AddFirmMemberRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Add an architect to a firm (firm admin only)."""
    member = await project_service.add_firm_member(
        db=db,
        firm_id=firm_id,
        email=request.email,
        user=current_user,
    )
    return {"message": f"Member {member.email} added to firm"}
