"""Pydantic schemas for projects and invitations."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.core.sanitize import sanitize_text


class ProjectCreate(BaseModel):
    """Request schema for creating a project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    firm_id: int | None = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class ProjectUpdate(BaseModel):
    """Request schema for updating a project."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_archived: bool | None = None

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class ProjectResponse(BaseModel):
    """Response schema for project list items."""

    id: int
    name: str
    description: str | None
    owner_id: int
    firm_id: int | None
    is_archived: bool
    file_count: int = 0
    milestone_count: int = 0
    completed_milestone_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Response schema for project detail view (includes nested milestones and files)."""

    milestones: list = []  # Will be list[MilestoneResponse]
    files: list = []  # Will be list[DesignFileResponse]


class ProjectDeleteRequest(BaseModel):
    """Request schema for permanently deleting a project.

    The user must type the project name to confirm — deletion removes all
    objects from storage and cannot be undone.
    """

    confirmation: str = Field(..., min_length=1, max_length=255)

    @field_validator("confirmation", mode="after")
    @classmethod
    def sanitize_confirmation(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class InviteClientRequest(BaseModel):
    """Request schema for inviting a client to a project."""

    email: EmailStr


class InvitationResponse(BaseModel):
    """Response schema for invitation data."""

    id: int
    email: str
    token: str
    expires_at: datetime
    is_used: bool
    created_at: datetime

    model_config = {"from_attributes": True}
