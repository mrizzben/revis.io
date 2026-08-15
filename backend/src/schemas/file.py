"""Pydantic schemas for file upload/download operations."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.sanitize import sanitize_text


class FileUploadUrlRequest(BaseModel):
    """Request to generate a presigned S3 upload URL (≤100MB)."""

    project_id: int
    milestone_id: int | None = None
    filename: str = Field(..., max_length=512)
    content_type: str = Field(..., max_length=127)
    file_size: int = Field(..., gt=0)
    # Upload a new revision of an existing design item (T1): stable identity.
    file_id: str | None = None
    revision_message: str | None = Field(None, max_length=512)
    name: str | None = Field(None, max_length=255)  # checkpoint name (T2)
    description: str | None = None  # issue note (T2)
    design_option_id: int | None = None  # upload into a design option (T5)

    @field_validator("revision_message", mode="after")
    @classmethod
    def sanitize_message(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class FileUploadUrlResponse(BaseModel):
    """Response with presigned upload URL and file metadata."""

    url: str
    key: str
    file_id: str


class MultipartInitiateRequest(BaseModel):
    """Request to initiate a multipart S3 upload (>100MB)."""

    project_id: int
    milestone_id: int | None = None
    filename: str = Field(..., max_length=512)
    content_type: str = Field(..., max_length=127)
    file_size: int = Field(..., gt=0)
    part_size: int = Field(..., ge=5_242_880)  # min 5MB
    # Upload a new revision of an existing design item (T1).
    file_id: str | None = None
    revision_message: str | None = Field(None, max_length=512)
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    design_option_id: int | None = None

    @field_validator("revision_message", mode="after")
    @classmethod
    def sanitize_message(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class MultipartInitiateResponse(BaseModel):
    """Response with multipart upload ID and metadata."""

    upload_id: str
    key: str
    file_id: str


class MultipartPartUrlsRequest(BaseModel):
    """Request to generate presigned URLs for specific parts."""

    key: str
    part_numbers: list[int] = Field(..., min_length=1, max_length=100)


class MultipartPartUrlsResponse(BaseModel):
    """Response with presigned URLs keyed by part number."""

    urls: dict[int, str]


class MultipartCompleteRequest(BaseModel):
    """Request to complete a multipart upload with ETags."""

    key: str
    parts: list[dict]


class DesignFileResponse(BaseModel):
    """Response schema for design file data."""

    id: str
    project_id: int
    milestone_id: int | None
    filename: str
    file_type: str
    content_type: str
    file_size: int
    thumbnail_status: str
    preview_status: str | None
    is_deleted: bool
    version_number: int = 1
    comment_count: int = 0
    uploaded_by: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VersionMetaUpdate(BaseModel):
    """Rename a checkpoint, attach an issue note, associate a milestone (T2)."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    milestone_id: int | None = None
    revision_message: str | None = Field(None, max_length=512)

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("description", mode="after")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v

    @field_validator("revision_message", mode="after")
    @classmethod
    def sanitize_message(cls, v: str | None) -> str | None:
        return sanitize_text(v) if isinstance(v, str) else v


class CompareRequest(BaseModel):
    """Select two revisions to compare (T4)."""

    from_version: int = Field(..., gt=0)
    to_version: int = Field(..., gt=0)
