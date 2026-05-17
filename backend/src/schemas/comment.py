"""Pydantic schemas for comments."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[int] = None

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class CommentUpdate(BaseModel):
    body: Optional[str] = Field(None, max_length=5000)
    is_resolved: Optional[bool] = None

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class CommentResponse(BaseModel):
    id: int
    file_id: str
    parent_id: int | None
    body: str
    is_resolved: bool
    author: Optional[dict] = None
    replies: list["CommentResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
