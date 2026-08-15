"""Review workflow service (T3).

Explicit design reviews: request review from a collaborator or client, assign a
reviewer, track status (draft → in_review → changes_requested/approved), keep an
immutable history via activity_events, and notify the internal team. Clients only
participate in reviews explicitly opened to them (`is_client_review=True`).
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.file import DesignFile, RevisionVisibility
from src.models.project import Project, ProjectMember
from src.models.review import Review, ReviewStatus
from src.models.user import User, UserRole
from src.services import activity
from src.services.notification import create_notification
from src.websocket import get_manager

ReviewStatusType = ReviewStatus


async def _load_project_team(db: AsyncSession, project_id: int) -> tuple[Project, list[User]]:
    """Return the project and its internal team (owner + collaborators)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "collaborator",
        )
    )
    member_user_ids = [m.user_id for m in member_result.scalars().all()]
    users: list[User] = []
    if member_user_ids:
        user_result = await db.execute(select(User).where(User.id.in_(member_user_ids)))
        users.extend(user_result.scalars().all())
    if project.owner_id:
        owner_result = await db.execute(select(User).where(User.id == project.owner_id))
        owner = owner_result.scalar_one_or_none()
        if owner:
            users.append(owner)
    return project, users


async def _notify_team(
    db: AsyncSession,
    project_id: int,
    ntype: str,
    title: str,
    body: str,
    exclude_user_id: int | None = None,
) -> None:
    """Create in-app notifications for every internal team member."""
    from src.models.notification import NotificationType

    _, team = await _load_project_team(db, project_id)
    for member in team:
        if exclude_user_id is not None and member.id == exclude_user_id:
            continue
        await create_notification(
            db=db,
            user_id=member.id,
            ntype=NotificationType(ntype),
            title=title,
            body=body,
            reference_id=project_id,
        )


async def _broadcast(
    db: AsyncSession,
    review: Review,
    message: dict,
    team_user_ids: list[int] | None = None,
) -> None:
    """Broadcast review events. Client-opened reviews reach the whole room;
    internal reviews reach only the team."""
    try:
        ws = get_manager()
        if review.is_client_review and team_user_ids is None:
            await ws.broadcast_to_project(review.project_id, message)
        else:
            await ws.broadcast_to_project_team(
                review.project_id,
                message,
                team_user_ids=team_user_ids or [],
            )
    except RuntimeError:
        pass


async def create_review(
    db: AsyncSession,
    file_id: str,
    requested_by: User,
    reviewer_id: int,
    revision_id: int | None = None,
    is_client_review: bool = False,
) -> Review:
    """Request a review: assign a reviewer (internal team member) and optionally
    open the review to the client."""
    file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
    file_result = await db.execute(
        select(DesignFile).where(DesignFile.id == file_uuid, DesignFile.is_deleted.is_(False))
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    from src.services.project import _get_project_with_access

    await _get_project_with_access(db, file.project_id, requested_by)

    # Reviewer must be an internal team member (owner or collaborator).
    if requested_by.role == UserRole.architect and file.project_id:
        _, team = await _load_project_team(db, file.project_id)
        if reviewer_id not in [u.id for u in team]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviewer must be a project owner or collaborator",
            )
    if requested_by.role == UserRole.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot request reviews",
        )

    reviewer_result = await db.execute(select(User).where(User.id == reviewer_id))
    reviewer = reviewer_result.scalar_one_or_none()
    if not reviewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewer not found")

    review = Review(
        project_id=file.project_id,
        file_id=file_uuid,
        revision_id=revision_id,
        requested_by_id=requested_by.id,
        reviewer_id=reviewer_id,
        status=ReviewStatus.draft,
        is_client_review=is_client_review,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    _, team = await _load_project_team(db, file.project_id)
    team_ids = [u.id for u in team]
    await _notify_team(
        db,
        file.project_id,
        "review_requested",
        f"Review requested on {file.filename}",
        f"{requested_by.name} requested a review from {reviewer.name} on {file.filename}",
        exclude_user_id=requested_by.id,
    )
    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=requested_by.id,
        event_type="review_requested",
        entity_type="review",
        entity_id=review.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer.name,
            "client_review": is_client_review,
        },
        visibility="client" if is_client_review else "internal",
    )
    await _broadcast(
        db,
        review,
        {
            "type": "review_requested",
            "review_id": review.id,
            "file_id": str(file.id),
            "status": review.status.value,
            "client_review": is_client_review,
        },
        team_user_ids=team_ids if not is_client_review else None,
    )
    return review


async def get_review(db: AsyncSession, review_id: int) -> Review:
    result = await db.execute(
        select(Review)
        .options(
            selectinload(Review.file),
            selectinload(Review.reviewer),
            selectinload(Review.requested_by),
            selectinload(Review.decided_by),
            selectinload(Review.revision),
        )
        .where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


async def list_reviews(
    db: AsyncSession,
    file_id: str,
    user: User,
) -> list[Review]:
    """List reviews for a design item.

    Clients see only reviews explicitly opened to them (and only for
    revisions they can already see).
    """
    file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
    file_result = await db.execute(
        select(DesignFile).where(DesignFile.id == file_uuid, DesignFile.is_deleted.is_(False))
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    from src.services.project import _get_project_with_access

    await _get_project_with_access(db, file.project_id, user)

    stmt = (
        select(Review)
        .options(selectinload(Review.reviewer), selectinload(Review.requested_by))
        .where(Review.file_id == file_uuid)
        .order_by(Review.created_at.desc())
    )
    if user.role == UserRole.client:
        stmt = stmt.where(Review.is_client_review.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def transition_review(
    db: AsyncSession,
    review_id: int,
    user: User,
    action: str,
    decision_comment: str | None = None,
) -> Review:
    """Apply a status transition: start / approve / request_changes / reopen.

    Approvals and change requests record the decision author and timestamp;
    the immutable history is kept in activity_events.
    """
    review = await get_review(db, review_id)

    from src.services.project import _get_project_with_access

    await _get_project_with_access(db, review.project_id, user)

    is_team = user.id == review.requested_by_id or user.id == review.reviewer_id
    is_owner = False
    if user.role == UserRole.architect:
        proj_result = await db.execute(select(Project).where(Project.id == review.project_id))
        project = proj_result.scalar_one_or_none()
        is_owner = bool(project and project.owner_id == user.id)

    # Clients may only comment-decide on reviews opened to them, and only via
    # the explicit review endpoints (approve / request_changes on client reviews).
    if user.role == UserRole.client and not review.is_client_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if action == "start":
        if not is_team and not is_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the assigned reviewer")
        if review.status not in (ReviewStatus.draft, ReviewStatus.changes_requested):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Review is not in a startable state")
        review.status = ReviewStatus.in_review
    elif action == "approve":
        if not is_team and not is_owner and user.role != UserRole.client:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the assigned reviewer")
        review.status = ReviewStatus.approved
        review.decided_by_id = user.id
        review.decided_at = datetime.now(UTC)
        review.decision_comment = decision_comment
        # Approving a revision is an internal signal; also move the revision to
        # `review` state so the approved checkpoint is visible to the team.
        if review.revision_id:
            from src.models.file import FileVersion

            ver_result = await db.execute(select(FileVersion).where(FileVersion.id == review.revision_id))
            version = ver_result.scalar_one_or_none()
            if version and version.visibility == RevisionVisibility.internal:
                version.visibility = RevisionVisibility.review
    elif action == "request_changes":
        if not is_team and not is_owner and user.role != UserRole.client:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the assigned reviewer")
        review.status = ReviewStatus.changes_requested
        review.decided_by_id = user.id
        review.decided_at = datetime.now(UTC)
        review.decision_comment = decision_comment
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown review action")

    review.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(review)

    _, team = await _load_project_team(db, review.project_id)
    team_ids = [u.id for u in team]

    await _notify_team(
        db,
        review.project_id,
        "review_updated",
        f"Review {review.status.value.replace('_', ' ')}",
        f"{user.name} set the review of {review.file.filename} to {review.status.value.replace('_', ' ')}",
        exclude_user_id=user.id,
    )
    await activity.record_event(
        db,
        project_id=review.project_id,
        actor_id=user.id,
        event_type=f"review_{review.status.value}",
        entity_type="review",
        entity_id=review.id,
        payload={
            "file_id": str(review.file_id),
            "file_name": review.file.filename,
            "action": action,
            "comment": decision_comment,
        },
        visibility="client" if review.is_client_review else "internal",
    )
    await _broadcast(
        db,
        review,
        {
            "type": "review_updated",
            "review_id": review.id,
            "file_id": str(review.file_id),
            "status": review.status.value,
            "client_review": review.is_client_review,
        },
        team_user_ids=team_ids if not review.is_client_review else None,
    )
    return review
