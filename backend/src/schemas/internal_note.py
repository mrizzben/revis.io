"""Pydantic schemas for internal notes, mentions, and replies."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class InternalNoteCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    mentions: list[int] = Field(default_factory=list)

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class InternalNoteReplyCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)

    @field_validator("body", mode="after")
    @classmethod
    def sanitize_body(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class MentionResponse(BaseModel):
    user_id: int
    name: str


class InternalNoteReplyResponse(BaseModel):
    id: int
    author: dict | None = None
    body: str
    parent_id: int
    created_at: datetime


class InternalNoteResponse(BaseModel):
    id: int
    author: dict | None = None
    body: str
    mentions: list[MentionResponse] = []
    replies: list[InternalNoteReplyResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
