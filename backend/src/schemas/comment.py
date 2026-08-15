"""Pydantic schemas for comments."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    parent_id: int | None = None
    # Revision the comment applies to; null → applies to all revisions (T1).
    version_id: int | None = None

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class CommentUpdate(BaseModel):
    body: str | None = Field(None, max_length=5000)
    is_resolved: bool | None = None

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class CommentResponse(BaseModel):
    id: int
    file_id: str
    parent_id: int | None
    version_id: int | None = None
    # 'revision' → applies to one revision; 'all' → applies to the item (T1).
    scope: str = "all"
    version_number: int | None = None
    body: str
    is_resolved: bool
    resolved_at: datetime | None = None
    resolved_by: dict | None = None
    author: dict | None = None
    replies: list["CommentResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
