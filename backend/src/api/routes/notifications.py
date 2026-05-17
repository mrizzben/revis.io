"""Notification API routes."""

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DBSession, get_current_user
from src.models.user import User
from src.services.notification import get_unread_notifications, mark_notification_read

router = APIRouter(prefix="", tags=["Notifications"])


@router.get(
    "/notifications",
    response_model=list[dict],
)
async def list_notifications(
    db: DBSession,
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    notifications = await get_unread_notifications(db, current_user.id, limit)
    return [
        {
            "id": n.id,
            "type": n.type.value,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "reference_id": n.reference_id,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


@router.post(
    "/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_read(
    notification_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    await mark_notification_read(db, notification_id, current_user.id)
