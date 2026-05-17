"""File storage service: S3 presigned URLs, upload/download, bucket management."""

import logging
import uuid
from datetime import timedelta
from typing import BinaryIO

import boto3
from botocore.client import Config
from fastapi import HTTPException, status

from src.core.config import settings

logger = logging.getLogger(__name__)


# Allowed file types and corresponding MIME types
ALLOWED_EXTENSIONS: set[str] = {
    "png", "jpg", "jpeg", "webp", "pdf",
    "dwg", "dxf", "skp", "rvt",
    "ifc", "obj", "stl",
}
MAX_FILE_SIZE = 1_073_741_824  # 1 GiB
MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB


def _get_s3_client(use_presigned_endpoint: bool = False):
    """Create a configured S3 client (or MinIO-compatible client).
    
    Args:
        use_presigned_endpoint: If True, use S3_PRESIGNED_ENDPOINT for generating
                               presigned URLs that browsers can use. Falls back
                               to S3_ENDPOINT if S3_PRESIGNED_ENDPOINT is not set.
    """
    kwargs = {
        "service_name": "s3",
        "config": Config(signature_version="s3v4"),
    }
    endpoint = settings.S3_ENDPOINT
    if use_presigned_endpoint and settings.S3_PRESIGNED_ENDPOINT:
        endpoint = settings.S3_PRESIGNED_ENDPOINT
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY
        kwargs["aws_secret_access_key"] = settings.S3_SECRET_KEY
        kwargs["region_name"] = settings.S3_REGION
    return boto3.client(**kwargs)


# Lazy-loaded S3 clients - initialized on first use, not at import time
_s3_client = None
_s3_presigned_client = None


def _get_lazy_s3_client():
    """Return the S3 client for internal operations, creating it on first use (lazy initialization)."""
    global _s3_client
    if _s3_client is None:
        logger.info("Initializing S3 client for internal operations", extra={"endpoint": settings.S3_ENDPOINT, "bucket": settings.S3_BUCKET})
        _s3_client = _get_s3_client(use_presigned_endpoint=False)
    return _s3_client


def _get_lazy_presigned_s3_client():
    """Return the S3 client for generating presigned URLs, creating it on first use.
    
    This client uses S3_PRESIGNED_ENDPOINT (external/browser-facing) if set,
    otherwise falls back to S3_ENDPOINT.
    """
    global _s3_presigned_client
    if _s3_presigned_client is None:
        presigned_endpoint = settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT
        logger.info("Initializing S3 client for presigned URLs", extra={"endpoint": presigned_endpoint, "bucket": settings.S3_BUCKET})
        _s3_presigned_client = _get_s3_client(use_presigned_endpoint=True)
    return _s3_presigned_client


async def ensure_bucket_exists() -> None:
    """Create the S3 bucket if it does not already exist."""
    s3 = _get_lazy_s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
        # Enable SSE-S3 encryption by default
        s3.put_bucket_encryption(
            Bucket=settings.S3_BUCKET,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256",
                        },
                    },
                ],
            },
        )


def validate_file_upload(
    filename: str,
    content_type: str,
    file_size: int,
) -> str:
    """Validate file metadata before generating presigned URL.

    Returns the file extension on success.
    Raises HTTPException on validation failure.
    """
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename has no extension",
        )

    ext = filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type .{ext} is not supported",
        )

    if file_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be positive",
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    return ext


def generate_s3_key(project_id: int, filename: str) -> str:
    """Generate a unique S3 object key: uploads/{project_id}/{uuid}/{filename}"""
    file_uuid = uuid.uuid4()
    return f"uploads/{project_id}/{file_uuid}/{filename}"


def create_presigned_upload_url(
    key: str,
    content_type: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned URL for a single PUT upload (≤100MB).
    
    Uses the presigned S3 client which connects to the external/browser-facing endpoint.
    """
    s3 = _get_lazy_presigned_s3_client()
    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error(
            "Failed to generate presigned upload URL",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def create_presigned_download_url(
    key: str,
    filename: str | None = None,
    content_type: str | None = None,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned URL for downloading a file.
    
    Uses the presigned S3 client which connects to the external/browser-facing endpoint.
    """
    s3 = _get_lazy_presigned_s3_client()
    try:
        params = {
            "Bucket": settings.S3_BUCKET,
            "Key": key,
        }
        if filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{filename}"'
            )
        if content_type:
            params["ResponseContentType"] = content_type
        url = s3.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error(
            "Failed to generate presigned download URL",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def initiate_multipart_upload(key: str, content_type: str) -> str:
    """Initiate a multipart upload and return the upload_id."""
    s3 = _get_lazy_s3_client()
    try:
        response = s3.create_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=key,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return response["UploadId"]
    except Exception as e:
        logger.error(
            "Failed to initiate multipart upload",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def create_multipart_part_urls(
    key: str,
    upload_id: str,
    part_numbers: list[int],
    expires_in: int = 3600,
) -> dict[int, str]:
    """Generate presigned URLs for multipart upload parts."""
    s3 = _get_lazy_s3_client()
    try:
        urls: dict[int, str] = {}
        for part_number in part_numbers:
            url = s3.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": settings.S3_BUCKET,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expires_in,
            )
            urls[part_number] = _fix_presigned_url(url)
        return urls
    except Exception as e:
        logger.error(
            "Failed to generate multipart presigned URLs",
            extra={"key": key, "upload_id": upload_id, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def complete_multipart_upload(
    key: str,
    upload_id: str,
    parts: list[dict],
) -> None:
    """Complete a multipart upload by providing the part list."""
    s3 = _get_lazy_s3_client()
    try:
        s3.complete_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
    except Exception as e:
        logger.error(
            "Failed to complete multipart upload",
            extra={"key": key, "upload_id": upload_id, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def abort_multipart_upload(key: str, upload_id: str) -> None:
    """Abort an incomplete multipart upload."""
    s3 = _get_lazy_s3_client()
    try:
        s3.abort_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=key,
            UploadId=upload_id,
        )
    except Exception as e:
        logger.error(
            "Failed to abort multipart upload",
            extra={"key": key, "upload_id": upload_id, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


def get_thumbnail_presigned_url(key: str | None, expires_in: int = 300) -> str | None:
    """Get a presigned URL for a thumbnail. Returns None if no thumbnail available.
    
    Uses the presigned S3 client which connects to the external/browser-facing endpoint.
    """
    if not key:
        return None
    s3 = _get_lazy_presigned_s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.error(
            "Failed to generate thumbnail presigned URL",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT},
        )
        # Don't raise - return None so caller can handle gracefully
        return None


def delete_s3_object(key: str) -> None:
    """Delete an object from S3."""
    s3 = _get_lazy_s3_client()
    try:
        s3.delete_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
        )
    except Exception as e:
        logger.error(
            "Failed to delete S3 object",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure MinIO is running.",
        ) from e


# ═══════════════════════════════════════════════════════════
# Database Operations (T028)
# ═══════════════════════════════════════════════════════════

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.file import DesignFile, FileVersion, ThumbnailStatus


async def create_file_record(
    db: AsyncSession,
    project_id: int,
    uploaded_by_id: int,
    filename: str,
    file_type: str,
    content_type: str,
    file_size: int,
    s3_key: str,
    milestone_id: int | None = None,
) -> DesignFile:
    """Create a design file record in the database."""
    file = DesignFile(
        id=uuid.uuid4(),
        project_id=project_id,
        milestone_id=milestone_id,
        uploaded_by_id=uploaded_by_id,
        filename=filename,
        file_type=file_type,
        content_type=content_type,
        file_size=file_size,
        s3_key=s3_key,
        thumbnail_status=ThumbnailStatus.pending,
    )
    db.add(file)
    await db.commit()
    await db.refresh(file)
    logger.info(
        "File upload initiated",
        extra={"file_id": str(file.id), "project_id": project_id, "file_name": filename, "size": file_size},
    )
    return file


async def get_file(
    db: AsyncSession,
    file_id: str,
) -> DesignFile:
    """Get a file by ID, including the uploader relationship."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by))
        .where(DesignFile.id == file_id, DesignFile.is_deleted.is_(False))
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


async def list_project_files(
    db: AsyncSession,
    project_id: int,
    milestone_id: int | None = None,
) -> list[DesignFile]:
    """List non-deleted files in a project, optionally filtered by milestone."""
    from sqlalchemy.orm import selectinload

    query = (
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by))
        .where(
            DesignFile.project_id == project_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    if milestone_id is not None:
        query = query.where(DesignFile.milestone_id == milestone_id)

    query = query.order_by(DesignFile.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def soft_delete_file(
    db: AsyncSession,
    file_id: str,
) -> None:
    """Soft-delete a design file."""
    file = await get_file(db, file_id)
    file.is_deleted = True
    file.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(
        "File soft-deleted",
        extra={"file_id": file_id, "project_id": file.project_id, "file_name": file.filename},
    )


async def complete_file_upload(
    db: AsyncSession,
    file_id: str,
) -> DesignFile:
    """Mark file upload as complete and trigger thumbnail generation queue."""
    file = await get_file(db, file_id)
    # The thumbnail_status is already 'pending', the ARQ worker will pick it up.
    # We could enqueue the ARQ job here but that requires redis connection.
    # For now, the frontend calls upload-complete to trigger processing.
    file.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(file)
    logger.info(
        "File upload completed",
        extra={"file_id": file_id, "project_id": file.project_id, "file_name": file.filename},
    )
    return file


async def create_file_version(
    db: AsyncSession,
    file_id: str,
    s3_key: str,
    file_size: int,
    uploaded_by_id: int,
) -> FileVersion:
    """Create a new version record for a file."""
    # Get current version count
    result = await db.execute(
        select(func.max(FileVersion.version_number)).where(
            FileVersion.file_id == file_id
        )
    )
    max_version = result.scalar() or 0

    version = FileVersion(
        file_id=file_id,
        version_number=max_version + 1,
        s3_key=s3_key,
        file_size=file_size,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version
