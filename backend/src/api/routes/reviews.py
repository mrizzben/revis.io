"""Review routes (T3)."""

from fastapi import APIRouter, Depends

from src.api.dependencies import DBSession, get_current_user
from src.models.user import User
from src.schemas.review import ReviewCreate, ReviewTransitionRequest
from src.services import review as review_service

router = APIRouter(tags=["Reviews"])


def _serialize(review) -> dict:
    return {
        "id": review.id,
        "project_id": review.project_id,
        "file_id": str(review.file_id),
        "revision_id": review.revision_id,
        "revision_number": review.revision.version_number if review.revision else None,
        "status": review.status.value,
        "is_client_review": review.is_client_review,
        "decision_comment": review.decision_comment,
        "requested_by": {"id": review.requested_by.id, "name": review.requested_by.name}
        if review.requested_by
        else None,
        "reviewer": {"id": review.reviewer.id, "name": review.reviewer.name}
        if review.reviewer
        else None,
        "decided_by": {"id": review.decided_by.id, "name": review.decided_by.name}
        if review.decided_by
        else None,
        "decided_at": review.decided_at,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


@router.post("/files/{file_id}/reviews", status_code=201)
async def create_review(
    file_id: str,
    data: ReviewCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    review = await review_service.create_review(
        db=db,
        file_id=file_id,
        requested_by=current_user,
        reviewer_id=data.reviewer_id,
        revision_id=data.revision_id,
        is_client_review=data.is_client_review,
    )
    return _serialize(review)


@router.get("/files/{file_id}/reviews")
async def list_reviews(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    reviews = await review_service.list_reviews(db, file_id, current_user)
    return [_serialize(r) for r in reviews]


@router.post("/reviews/{review_id}/transition")
async def transition_review(
    review_id: int,
    data: ReviewTransitionRequest,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    review = await review_service.transition_review(
        db, review_id, current_user, data.action, data.comment
    )
    return _serialize(review)
