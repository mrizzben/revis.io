"""Pydantic schemas for to-dos."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    assignee_id: int | None = None

    @field_validator("title", "description", mode="after")
    @classmethod
    def sanitize_texts(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    status: str | None = None
    assignee_id: int | None = None

    @field_validator("title", "description", mode="after")
    @classmethod
    def sanitize_texts(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class TodoResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    assignee: dict | None = None
    created_by: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
