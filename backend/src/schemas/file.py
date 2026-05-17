"""Pydantic schemas for file upload/download operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FileUploadUrlRequest(BaseModel):
    """Request to generate a presigned S3 upload URL (≤100MB)."""

    project_id: int
    milestone_id: Optional[int] = None
    filename: str = Field(..., max_length=512)
    content_type: str = Field(..., max_length=127)
    file_size: int = Field(..., gt=0)


class FileUploadUrlResponse(BaseModel):
    """Response with presigned upload URL and file metadata."""

    url: str
    key: str
    file_id: str


class MultipartInitiateRequest(BaseModel):
    """Request to initiate a multipart S3 upload (>100MB)."""

    project_id: int
    milestone_id: Optional[int] = None
    filename: str = Field(..., max_length=512)
    content_type: str = Field(..., max_length=127)
    file_size: int = Field(..., gt=0)
    part_size: int = Field(..., ge=5_242_880)  # min 5MB


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
    uploaded_by: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
