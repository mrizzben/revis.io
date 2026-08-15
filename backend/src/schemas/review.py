"""Pydantic schemas for reviews (T3)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class ReviewCreate(BaseModel):
    """Request a review of a design item."""

    reviewer_id: int
    revision_id: int | None = None
    is_client_review: bool = False
    note: str | None = Field(None, max_length=2000)

    @field_validator("note", mode="after")
    @classmethod
    def sanitize_note(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class ReviewTransitionRequest(BaseModel):
    """Apply a review status transition."""

    action: str = Field(..., pattern="^(start|approve|request_changes)$")
    comment: str | None = Field(None, max_length=2000)

    @field_validator("comment", mode="after")
    @classmethod
    def sanitize_comment(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class ReviewResponse(BaseModel):
    id: int
    project_id: int
    file_id: str
    revision_id: int | None
    revision_number: int | None = None
    status: str
    is_client_review: bool
    decision_comment: str | None
    requested_by: dict | None = None
    reviewer: dict | None = None
    decided_by: dict | None = None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
