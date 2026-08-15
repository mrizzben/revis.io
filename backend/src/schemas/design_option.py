"""Pydantic schemas for design options (T5)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class DesignOptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class DesignOptionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_current: bool | None = None
    is_archived: bool | None = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class ForkItemRequest(BaseModel):
    """Fork a design item into an option (copies its revision history)."""

    file_id: str = Field(..., min_length=1)


class DesignOptionResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    is_current: bool
    is_archived: bool
    file_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
