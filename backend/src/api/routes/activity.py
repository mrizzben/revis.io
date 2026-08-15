"""Activity / audit timeline routes (T6)."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import DBSession, get_current_user
from src.models.user import User
from src.services import activity as activity_service

router = APIRouter(tags=["Activity"])


@router.get("/projects/{project_id}/activity")
async def list_activity(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    """Project activity timeline.

    Internal users see internal + client events; clients see only client-visible
    events — the same visibility rules as the underlying entities (T6).
    """
    await activity_service.ensure_activity_access(db, project_id, current_user)
    return await activity_service.list_events(
        db, project_id, current_user, event_type=event_type, limit=limit
    )
