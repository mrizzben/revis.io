"""Pydantic schemas for milestones."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    position: Optional[int] = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    position: Optional[int] = None
    is_completed: Optional[bool] = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class MilestoneResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    position: int
    is_completed: bool
    completed_at: datetime | None
    file_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
