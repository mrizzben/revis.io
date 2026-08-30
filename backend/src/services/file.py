"""File storage service: S3 presigned URLs, upload/download, bucket management."""

import logging
import uuid

import boto3
from botocore.client import Config
from fastapi import HTTPException, status

from src.core.config import settings

logger = logging.getLogger(__name__)


# Allowed file types and corresponding MIME types
ALLOWED_EXTENSIONS: set[str] = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "pdf",
    "dwg",
    "dxf",
    "skp",
    "rvt",
    "ifc",
    "obj",
    "stl",
}
MAX_FILE_SIZE = 1_073_741_824  # 1 GiB
MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB


def _get_s3_client(use_presigned_endpoint: bool = False):
    """Create a configured S3 client (RustFS or any S3-compatible store).

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
        logger.info(
            "Initializing S3 client for internal operations",
            extra={"endpoint": settings.S3_ENDPOINT, "bucket": settings.S3_BUCKET},
        )
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
        logger.info(
            "Initializing S3 client for presigned URLs",
            extra={"endpoint": presigned_endpoint, "bucket": settings.S3_BUCKET},
        )
        _s3_presigned_client = _get_s3_client(use_presigned_endpoint=True)
    return _s3_presigned_client


def _presigned_endpoint() -> str | None:
    """External/browser-facing endpoint used for presigned URLs."""
    return settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT


async def ensure_bucket_exists() -> None:
    """Create the storage bucket if it does not already exist."""
    s3 = _get_lazy_s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        # RustFS has no SSE-S3 (AES256 bucket encryption); it encrypts at
        # rest itself, so the bucket is created without extra configuration.
        s3.create_bucket(Bucket=settings.S3_BUCKET)


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
            extra={
                "key": key,
                "error": str(e),
                "endpoint": _presigned_endpoint(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
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
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
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
            extra={
                "key": key,
                "error": str(e),
                "endpoint": _presigned_endpoint(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
        ) from e


def initiate_multipart_upload(key: str, content_type: str) -> str:
    """Initiate a multipart upload and return the upload_id."""
    s3 = _get_lazy_s3_client()
    try:
        response = s3.create_multipart_upload(
            Bucket=settings.S3_BUCKET,
            Key=key,
            ContentType=content_type,
        )
        return response["UploadId"]
    except Exception as e:
        logger.error(
            "Failed to initiate multipart upload",
            extra={"key": key, "error": str(e), "endpoint": settings.S3_ENDPOINT},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
        ) from e


def _fix_presigned_url(url: str) -> str:
    """Rewrite a presigned URL's host to the browser-facing endpoint.

    Multipart part URLs are generated with the internal S3 client; browsers
    must PUT to them via the external/presigned endpoint instead. No-op when
    no presigned endpoint is configured.
    """
    target = settings.S3_PRESIGNED_ENDPOINT or settings.S3_ENDPOINT
    if not target:
        return url
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    target_parts = urlsplit(target)
    if parts.netloc == target_parts.netloc:
        return url
    return urlunsplit((parts.scheme, target_parts.netloc, parts.path, parts.query, parts.fragment))


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
            extra={
                "key": key,
                "upload_id": upload_id,
                "error": str(e),
                "endpoint": settings.S3_ENDPOINT,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
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
            extra={
                "key": key,
                "upload_id": upload_id,
                "error": str(e),
                "endpoint": settings.S3_ENDPOINT,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
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
            extra={
                "key": key,
                "upload_id": upload_id,
                "error": str(e),
                "endpoint": settings.S3_ENDPOINT,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
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
            extra={
                "key": key,
                "error": str(e),
                "endpoint": _presigned_endpoint(),
            },
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
            detail="Storage service unavailable. Please ensure the object store (RustFS) is running.",
        ) from e


# ═══════════════════════════════════════════════════════════
# Database Operations (T028)
# ═══════════════════════════════════════════════════════════

from datetime import UTC, datetime

from sqlalchemy import func, select
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
    design_option_id: int | None = None,
) -> DesignFile:
    """Create a design file record in the database."""
    file = DesignFile(
        id=uuid.uuid4(),
        project_id=project_id,
        milestone_id=milestone_id,
        design_option_id=design_option_id,
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
        extra={
            "file_id": str(file.id),
            "project_id": project_id,
            "file_name": filename,
            "size": file_size,
        },
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
        .where(DesignFile.id == uuid.UUID(file_id), DesignFile.is_deleted.is_(False))
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
    file.updated_at = datetime.now(UTC)
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
    file.updated_at = datetime.now(UTC)
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
    file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
    result = await db.execute(
        select(func.max(FileVersion.version_number)).where(FileVersion.file_id == file_uuid)
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


# ═══════════════════════════════════════════════════════════
# Revision lifecycle (T1 / T2 / T7 / T8)
# ═══════════════════════════════════════════════════════════

import hashlib
import socket
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from src.models.file import (
    CLIENT_VISIBLE_VISIBILITIES,
    DesignFile,
    FileVersion,
    RevisionVisibility,
    ScanStatus,
)

# ── Object integrity helpers (T8) ────────────────────────────


def compute_object_hash(s3: Any, bucket: str, key: str) -> str:
    """Stream an object from S3 and return its SHA-256 hex digest.

    Raises HTTPException(409) if the object is missing (interrupted upload).
    """
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as e:  # NoSuchKey / network
        logger.error("Hash: object unavailable", extra={"key": key, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uploaded object not found in storage — the upload was interrupted. Please re-upload.",
        ) from e
    digest = hashlib.sha256()
    try:
        for chunk in iter(lambda: obj["Body"].read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        obj["Body"].close()
    return digest.hexdigest()


_MAGIC_BYTES: dict[str, tuple[bytes, int]] = {
    # file_type -> (signature, offset)
    "pdf": (b"%PDF", 0),
    "png": (b"\x89PNG\r\n\x1a\n", 0),
    "jpg": (b"\xff\xd8\xff", 0),
    "jpeg": (b"\xff\xd8\xff", 0),
    "webp": (b"WEBP", 8),
    "obj": (b"", -1),  # plain text — no reliable magic
    "stl": (b"solid", 0),  # ASCII STL; binary STL has no magic
    "ifc": (b"", -1),
    "dwg": (b"AC10", 0),
    "dxf": (b"", -1),
    "skp": (b"", -1),
    "rvt": (b"", -1),
}


def verify_content_mime(s3: Any, bucket: str, key: str, file_type: str) -> bool:
    """Validate object content against its declared type using magic bytes.

    Returns True when content matches (or the type has no reliable magic).
    """
    signature, offset = _MAGIC_BYTES.get(file_type, (b"", -1))
    if offset < 0 or not signature:
        return True
    try:
        obj = s3.get_object(
            Bucket=bucket, Key=key, Range=f"bytes={offset}-{offset + len(signature) + 8}"
        )
        head = obj["Body"].read(len(signature) + 8)
        obj["Body"].close()
    except Exception as e:
        logger.error("MIME check: read failed", extra={"key": key, "error": str(e)})
        return True
    return head.startswith(signature)


def scan_object_with_clamd(s3: Any, bucket: str, key: str, file_size: int) -> ScanStatus:
    """Stream the object to clamd (TCP protocol) and report the verdict.

    - No CLAMD_HOST configured → skipped (dev/deploy choice).
    - Object larger than MALWARE_SCAN_MAX_SIZE → skipped (out-of-band scan).
    - clamd unreachable / error → `error` (issue is blocked until resolved).
    """
    if not settings.CLAMD_HOST:
        return ScanStatus.skipped
    if file_size > settings.MALWARE_SCAN_MAX_SIZE:
        return ScanStatus.skipped

    # clamd INSTREAM protocol: "zINSTREAM\0" then length-prefixed chunks, "0\0" to finish.
    try:
        with socket.create_connection(
            (settings.CLAMD_HOST, settings.CLAMD_PORT), timeout=60
        ) as sock:
            sock.sendall(b"zINSTREAM\0")
            obj = s3.get_object(Bucket=bucket, Key=key)
            try:
                for chunk in iter(lambda: obj["Body"].read(1024 * 1024), b""):
                    if not chunk:
                        continue
                    sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
            finally:
                obj["Body"].close()
            sock.sendall(b"\0\0\0\0")
            response = sock.recv(4096).decode(errors="replace").strip()
    except Exception as e:
        logger.error("ClamAV scan failed", extra={"key": key, "error": str(e)})
        return ScanStatus.error

    if "FOUND" in response.upper():
        return ScanStatus.infected
    if "OK" in response.upper():
        return ScanStatus.clean
    return ScanStatus.error


def object_exists(s3: Any, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


# ── Deduplication (T8: "detect duplicate uploads where practical") ──


async def _find_version_with_hash(db: AsyncSession, content_hash: str) -> FileVersion | None:
    result = await db.execute(
        select(FileVersion)
        .where(FileVersion.content_hash == content_hash)
        .order_by(FileVersion.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _finalize_version(db: AsyncSession, version: FileVersion) -> FileVersion:
    """Hash, verify content, scan and dedupe an uploaded revision's object.

    Runs at upload-complete (trust boundary): the browser already wrote the
    object to S3 under a fresh immutable key; this function validates that
    content, computes its hash, and dedupes against existing revisions.
    """
    s3 = _get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    file = await get_file(db, str(version.file_id))

    # Interrupted upload → the object is missing → fail clearly, don't record a version.
    if not object_exists(s3, bucket, version.s3_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uploaded object not found in storage — the upload was interrupted. Please re-upload.",
        )

    content_hash = compute_object_hash(s3, bucket, version.s3_key)
    version.content_hash = content_hash
    version.mime_valid = verify_content_mime(s3, bucket, version.s3_key, file.file_type)

    # Dedupe: identical content already stored → reuse its immutable key.
    existing = await _find_version_with_hash(db, content_hash)
    if existing is not None and str(existing.file_id) != str(version.file_id):
        try:
            s3.delete_object(Bucket=bucket, Key=version.s3_key)
        except Exception as e:
            logger.error("Dedupe cleanup failed", extra={"key": version.s3_key, "error": str(e)})
        version.s3_key = existing.s3_key
        version.file_size = existing.file_size

    version.scan_status = scan_object_with_clamd(s3, bucket, version.s3_key, version.file_size)
    await db.commit()
    await db.refresh(version)
    return version


async def create_revision(
    db: AsyncSession,
    file_id: str,
    uploaded_by_id: int,
    revision_message: str | None = None,
    name: str | None = None,
    description: str | None = None,
    milestone_id: int | None = None,
    s3_key: str | None = None,
    file_size: int | None = None,
) -> FileVersion:
    """Record a completed upload as the next revision of a design item and
    promote it to the item's current revision.

    `s3_key`/`file_size` describe the newly uploaded object (for new items the
    values already on the file record are used). New revisions always start as
    `internal` (T7: issuing is an explicit action, never a side effect of
    upload).
    """
    file = await get_file(db, file_id)
    file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
    result = await db.execute(
        select(func.max(FileVersion.version_number)).where(FileVersion.file_id == file_uuid)
    )
    max_version = result.scalar() or 0

    object_key = s3_key or file.s3_key
    object_size = file_size if file_size is not None else file.file_size
    version = FileVersion(
        file_id=file_uuid,
        version_number=max_version + 1,
        s3_key=object_key,
        file_size=object_size,
        uploaded_by_id=uploaded_by_id,
        revision_message=revision_message.strip() if revision_message else None,
        name=name.strip() if name else None,
        description=description.strip() if description else None,
        visibility=RevisionVisibility.internal,
        milestone_id=milestone_id if milestone_id is not None else file.milestone_id,
        scan_status=ScanStatus.pending,
    )
    db.add(version)
    await db.flush()

    await _finalize_version(db, version)

    # Promote: new upload becomes the current revision (new content → new thumbnails).
    file.current_version_id = version.id
    file.s3_key = version.s3_key
    file.file_size = version.file_size
    file.milestone_id = version.milestone_id
    file.thumbnail_status = ThumbnailStatus.pending
    file.thumbnail_small_key = None
    file.thumbnail_medium_key = None
    file.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(version)
    logger.info(
        "Revision recorded",
        extra={
            "file_id": file_id,
            "version": version.version_number,
            "hash": version.content_hash,
            "scan": version.scan_status.value,
            "size": version.file_size,
        },
    )
    return version


# ── Version accessors ────────────────────────────────────────


async def get_version(
    db: AsyncSession,
    file_id: str,
    version_number: int,
) -> FileVersion:
    file = await get_file(db, file_id)
    result = await db.execute(
        select(FileVersion)
        .options(
            selectinload(FileVersion.uploaded_by),
            selectinload(FileVersion.milestone),
            selectinload(FileVersion.issued_by),
            selectinload(FileVersion.file),
        )
        .where(
            FileVersion.file_id == file.id,
            FileVersion.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    return version


async def list_versions(
    db: AsyncSession,
    file_id: str,
    include_archived: bool = False,
) -> list[FileVersion]:
    """List an item's revisions for an internal user (all but archived)."""
    file = await get_file(db, file_id)
    stmt = (
        select(FileVersion)
        .options(
            selectinload(FileVersion.uploaded_by),
            selectinload(FileVersion.milestone),
            selectinload(FileVersion.issued_by),
            selectinload(FileVersion.file),
        )
        .where(FileVersion.file_id == file.id)
    )
    if not include_archived:
        stmt = stmt.where(FileVersion.visibility != RevisionVisibility.archived)
    stmt = stmt.order_by(FileVersion.version_number)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_client_versions(
    db: AsyncSession,
    file_id: str,
) -> list[FileVersion]:
    """Revisions a client may see: everything the architect intentionally issued
    (client_issued or superseded), newest first."""
    file = await get_file(db, file_id)
    result = await db.execute(
        select(FileVersion)
        .options(
            selectinload(FileVersion.uploaded_by),
            selectinload(FileVersion.milestone),
            selectinload(FileVersion.issued_by),
            selectinload(FileVersion.file),
        )
        .where(
            FileVersion.file_id == file.id,
            FileVersion.visibility.in_(CLIENT_VISIBLE_VISIBILITIES),
        )
        .order_by(FileVersion.version_number.desc())
    )
    return list(result.scalars().all())


# ── Lifecycle transitions (T2 / T7) ──────────────────────────


def _issuable(version: FileVersion) -> bool:
    return version.visibility in (
        RevisionVisibility.internal,
        RevisionVisibility.review,
        RevisionVisibility.client_issued,
        RevisionVisibility.superseded,
    )


async def issue_version(
    db: AsyncSession,
    file_id: str,
    version_number: int,
    actor: Any,
) -> FileVersion:
    """Explicitly issue a revision to the client.

    The revision becomes client_issued; any previously client_issued revision
    of the same item becomes superseded. Refuses if the object failed its
    malware scan (T8: nothing infected is ever made available).
    """
    version = await get_version(db, file_id, version_number)
    if not _issuable(version):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This revision cannot be issued"
        )
    if version.scan_status == ScanStatus.infected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This revision failed malware scanning and cannot be issued.",
        )

    result = await db.execute(
        select(FileVersion).where(
            FileVersion.file_id == version.file_id,
            FileVersion.visibility == RevisionVisibility.client_issued,
            FileVersion.id != version.id,
        )
    )
    for previous in result.scalars().all():
        previous.visibility = RevisionVisibility.superseded
        previous.superseded_at = datetime.now(UTC)
        previous.superseded_by_id = actor.id

    version.visibility = RevisionVisibility.client_issued
    version.issued_by_id = actor.id
    version.issued_at = datetime.now(UTC)
    version.superseded_at = None
    version.superseded_by_id = None
    await db.commit()
    await db.refresh(version)
    return version


async def supersede_version(
    db: AsyncSession,
    file_id: str,
    version_number: int,
    actor: Any,
) -> FileVersion:
    """Explicitly mark a revision superseded (kept, never deleted)."""
    version = await get_version(db, file_id, version_number)
    if version.visibility in (RevisionVisibility.archived, RevisionVisibility.internal):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This revision cannot be superseded"
        )
    version.visibility = RevisionVisibility.superseded
    version.superseded_at = datetime.now(UTC)
    version.superseded_by_id = actor.id
    await db.commit()
    await db.refresh(version)
    return version


async def archive_version(
    db: AsyncSession,
    file_id: str,
    version_number: int,
) -> FileVersion:
    """Archive a revision: hidden from normal views, retained for audit/history."""
    version = await get_version(db, file_id, version_number)
    version.visibility = RevisionVisibility.archived
    await db.commit()
    await db.refresh(version)
    return version


async def set_review_state(
    db: AsyncSession,
    file_id: str,
    version_number: int,
    in_review: bool,
) -> FileVersion:
    """Move a revision between internal draft and internal review (T2 states)."""
    version = await get_version(db, file_id, version_number)
    if version.visibility not in (RevisionVisibility.internal, RevisionVisibility.review):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can enter internal review"
        )
    version.visibility = RevisionVisibility.review if in_review else RevisionVisibility.internal
    await db.commit()
    await db.refresh(version)
    return version


async def update_version_meta(
    db: AsyncSession,
    file_id: str,
    version_number: int,
    name: str | None = None,
    description: str | None = None,
    milestone_id: int | None = None,
    revision_message: str | None = None,
) -> FileVersion:
    """Rename a checkpoint, attach an issue note, associate a milestone."""
    version = await get_version(db, file_id, version_number)
    if name is not None:
        version.name = name.strip() or None
    if description is not None:
        version.description = description.strip() or None
    if milestone_id is not None:
        version.milestone_id = milestone_id or None
    if revision_message is not None:
        version.revision_message = revision_message.strip() or None
    await db.commit()
    await db.refresh(version)
    return version


async def restore_version(
    db: AsyncSession,
    file_id: str,
    version_number: int,
    actor: Any,
) -> FileVersion:
    """Restore a prior revision as current without deleting history.

    Restoring an issued/superseded revision re-promotes it to client_issued
    (it is again the active deliverable); restoring a draft keeps it internal.
    Archived revisions cannot be restored via this action.
    """
    version = await get_version(db, file_id, version_number)
    if version.visibility == RevisionVisibility.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Archived revisions cannot be restored"
        )

    file = await get_file(db, file_id)
    previous_current = (
        await db.get(FileVersion, file.current_version_id) if file.current_version_id else None
    )

    if version.visibility == RevisionVisibility.superseded:
        # Re-promote: it becomes the active client deliverable again.
        version.visibility = RevisionVisibility.client_issued
        version.issued_by_id = actor.id
        version.issued_at = datetime.now(UTC)
        version.superseded_at = None
        version.superseded_by_id = None
        version.restored_from_superseded = True
        if (
            previous_current
            and previous_current.visibility == RevisionVisibility.client_issued
            and previous_current.id != version.id
        ):
            previous_current.visibility = RevisionVisibility.superseded
            previous_current.superseded_at = datetime.now(UTC)
            previous_current.superseded_by_id = actor.id
    elif version.visibility == RevisionVisibility.client_issued:
        if (
            previous_current
            and previous_current.visibility == RevisionVisibility.client_issued
            and previous_current.id != version.id
        ):
            previous_current.visibility = RevisionVisibility.superseded
            previous_current.superseded_at = datetime.now(UTC)
            previous_current.superseded_by_id = actor.id

    file.current_version_id = version.id
    file.s3_key = version.s3_key
    file.file_size = version.file_size
    file.milestone_id = version.milestone_id
    file.thumbnail_status = ThumbnailStatus.pending
    file.thumbnail_small_key = None
    file.thumbnail_medium_key = None
    file.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(version)
    return version


# ── Payload builders (role-aware) ───────────────────────────


def _user_brief(user: Any) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }


def build_version_payload(
    version: FileVersion,
    current_version_id: int | None = None,
    with_download_url: bool = False,
) -> dict:
    """Serialize a revision. `with_download_url` presigns a download link."""
    milestone_name = None
    if version.milestone is not None:
        milestone_name = version.milestone.name
    payload: dict[str, Any] = {
        "id": version.id,
        "file_id": str(version.file_id),
        "version_number": version.version_number,
        "file_size": version.file_size,
        "content_hash": version.content_hash,
        "revision_message": version.revision_message,
        "name": version.name,
        "description": version.description,
        "visibility": version.visibility.value,
        "scan_status": version.scan_status.value,
        "mime_valid": version.mime_valid,
        "restored_from_superseded": version.restored_from_superseded,
        "milestone_id": version.milestone_id,
        "milestone_name": milestone_name,
        "issued_at": version.issued_at,
        "superseded_at": version.superseded_at,
        "uploaded_by": _user_brief(version.uploaded_by) if version.uploaded_by else None,
        "issued_by": _user_brief(version.issued_by) if version.issued_by else None,
        "is_current": current_version_id is not None and version.id == current_version_id,
        "created_at": version.created_at,
    }
    if with_download_url:
        payload["download_url"] = create_presigned_download_url(
            key=version.s3_key,
            filename=f"{version.file.filename}" if version.file else None,
            content_type=version.file.content_type if version.file else None,
        )
    return payload


def effective_client_version(versions: list[FileVersion]) -> FileVersion | None:
    """The revision a client sees as 'current': latest issued, else latest superseded."""
    issued = [v for v in versions if v.visibility == RevisionVisibility.client_issued]
    if issued:
        return max(issued, key=lambda v: v.version_number)
    superseded = [v for v in versions if v.visibility == RevisionVisibility.superseded]
    if superseded:
        return max(superseded, key=lambda v: v.version_number)
    return None


async def build_file_payload(
    db: AsyncSession,
    file: DesignFile,
    user: Any,
    include_versions: bool = True,
) -> dict[str, Any]:
    """Role-aware file payload for project detail / file list endpoints.

    Internal users see the true current revision and all revisions.
    Clients see only the item's issued history, with the latest issued
    revision presented as current. Files with no issued revision are never
    returned to clients (caller filters).
    """
    from src.models.user import UserRole

    is_client = user.role == UserRole.client

    if is_client:
        versions = await list_client_versions(db, str(file.id))
        current = effective_client_version(versions)
        visible_versions = versions
    else:
        versions = await list_versions(db, str(file.id))
        current = None
        if file.current_version_id:
            current = next((v for v in versions if v.id == file.current_version_id), None)
        visible_versions = versions

    current_payload = build_version_payload(current) if current else None

    # Comment count for the visible current revision: all-revision comments
    # plus comments scoped to the revision the viewer sees as current.
    from src.models.comment import Comment

    comment_count = 0
    if current:
        result = await db.execute(
            select(func.count())
            .select_from(Comment)
            .where(
                Comment.file_id == file.id,
                or_(Comment.version_id.is_(None), Comment.version_id == current.id),
            )
        )
        comment_count = result.scalar() or 0

    option = file.design_option
    payload: dict[str, Any] = {
        "id": str(file.id),
        "project_id": file.project_id,
        "milestone_id": file.milestone_id,
        "design_option_id": file.design_option_id,
        "design_option_name": option.name if option else None,
        "parent_file_id": str(file.parent_file_id) if file.parent_file_id else None,
        "filename": file.filename,
        "file_type": file.file_type,
        "content_type": file.content_type,
        "file_size": file.file_size,
        "thumbnail_status": file.thumbnail_status.value,
        "preview_status": file.preview_status,
        "is_deleted": file.is_deleted,
        "version_number": current.version_number if current else 0,
        "version_count": len(visible_versions),
        "current_version": current_payload,
        "comment_count": comment_count,
        "uploaded_by": {
            "id": file.uploaded_by.id,
            "email": file.uploaded_by.email,
            "name": file.uploaded_by.name,
            "role": file.uploaded_by.role.value
            if hasattr(file.uploaded_by.role, "value")
            else file.uploaded_by.role,
            "firm_id": file.uploaded_by.firm_id,
            "is_firm_admin": file.uploaded_by.is_firm_admin,
            "is_verified": file.uploaded_by.is_verified,
            "created_at": file.uploaded_by.created_at.isoformat()
            if file.uploaded_by.created_at
            else None,
        }
        if file.uploaded_by
        else None,
        "created_at": file.created_at,
        "updated_at": file.updated_at,
    }
    if include_versions:
        current_id = current.id if current else file.current_version_id
        payload["versions"] = [
            build_version_payload(v, current_version_id=current_id, with_download_url=is_client)
            for v in visible_versions
        ]
    return payload


async def build_version_list_payload(
    db: AsyncSession,
    file: DesignFile,
    versions: list[FileVersion],
    current_version_id: int | None = None,
) -> list[dict]:
    """Serialize a list of versions without per-item download URLs."""
    return [build_version_payload(v, current_version_id=current_version_id) for v in versions]


# ── Comparison (T4) ──────────────────────────────────────────

COMPARABLE_TYPES = {"pdf", "png", "jpg", "jpeg", "webp"}


def build_comparison_payload(
    file: DesignFile,
    from_version: FileVersion,
    to_version: FileVersion,
) -> dict[str, Any]:
    """Comparison metadata + presigned view URLs for two revisions.

    Unsupported formats get an explicit `unsupported` explanation instead of
    failing silently (T4: unsupported formats explain that comparison is
    unavailable).
    """
    supported = file.file_type in COMPARABLE_TYPES
    return {
        "file_id": str(file.id),
        "file_type": file.file_type,
        "supported": supported,
        "explanation": (
            None
            if supported
            else (
                f"Live comparison is not available for {file.file_type.upper()} files. "
                "Download both revisions and compare them in your design application."
            )
        ),
        "from": build_version_payload(from_version, with_download_url=supported),
        "to": build_version_payload(to_version, with_download_url=supported),
    }


# ── Storage lifecycle (T8) ───────────────────────────────────


async def report_storage_usage(
    db: AsyncSession,
    project_id: int | None = None,
    firm_id: int | None = None,
) -> dict[str, Any]:
    """Storage usage by project (and firm rollup). Counts every revision's
    declared size; deduplicated content may over-count slightly (documented)."""
    from src.models.project import Project

    stmt = (
        select(
            DesignFile.project_id,
            func.sum(FileVersion.file_size),
            func.count(FileVersion.id),
        )
        .join(FileVersion, FileVersion.file_id == DesignFile.id)
        .where(DesignFile.is_deleted.is_(False))
    )
    if project_id is not None:
        stmt = stmt.where(DesignFile.project_id == project_id)
    stmt = stmt.group_by(DesignFile.project_id)
    result = await db.execute(stmt)
    rows = result.all()

    by_project = [
        {"project_id": pid, "total_bytes": total, "revision_count": count}
        for pid, total, count in rows
    ]

    if firm_id is not None:
        proj_result = await db.execute(select(Project.id).where(Project.firm_id == firm_id))
        firm_projects = {row[0] for row in proj_result.all()}
        firm_rows = [r for r in by_project if r["project_id"] in firm_projects]
        return {
            "firm_id": firm_id,
            "total_bytes": sum(r["total_bytes"] or 0 for r in firm_rows),
            "revision_count": sum(r["revision_count"] or 0 for r in firm_rows),
            "project_count": len(firm_rows),
            "by_project": firm_rows,
        }

    return {
        "project_id": project_id,
        "total_bytes": sum(r["total_bytes"] or 0 for r in by_project),
        "revision_count": sum(r["revision_count"] or 0 for r in by_project),
        "by_project": by_project,
    }


def list_orphaned_objects(
    s3: Any, bucket: str, known_keys: set[str], prefix: str = "uploads/"
) -> list[str]:
    """S3 objects under `uploads/` not referenced by any revision record."""
    orphaned: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"] not in known_keys:
                orphaned.append(obj["Key"])
    return orphaned


def list_abandoned_multipart_uploads(
    s3: Any,
    bucket: str,
    older_than: datetime,
) -> list[dict[str, Any]]:
    """Incomplete multipart uploads not initialized within the retention window."""
    abandoned: list[dict[str, Any]] = []
    paginator = s3.get_paginator("list_multipart_uploads")
    for page in paginator.paginate(Bucket=bucket):
        for upload in page.get("Uploads", []):
            initialized = upload.get("Initiated")
            if initialized is None:
                continue
            if isinstance(initialized, str):
                initialized = datetime.fromisoformat(initialized.replace("Z", "+00:00"))
            if initialized < older_than:
                abandoned.append(
                    {
                        "key": upload["Key"],
                        "upload_id": upload["UploadId"],
                        "initiated": initialized,
                    }
                )
    return abandoned


async def get_all_revision_keys(db: AsyncSession) -> set[str]:
    result = await db.execute(select(FileVersion.s3_key))
    return {row[0] for row in result.all()}


async def purge_soft_deleted(db: AsyncSession, older_than: datetime) -> int:
    """Hard-delete design items soft-deleted before the retention window.

    S3 objects are deleted only when no remaining revision references them
    (deduplicated content is preserved).
    """
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(DesignFile)
        .options(selectinload(DesignFile.versions))
        .where(
            DesignFile.is_deleted.is_(True),
            DesignFile.updated_at < older_than,
        )
    )
    files = list(result.scalars().all())
    s3 = _get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    purged = 0
    for file in files:
        keys = [v.s3_key for v in file.versions]
        await db.delete(file)
        await db.flush()
        for key in keys:
            count = await db.execute(
                select(func.count()).select_from(FileVersion).where(FileVersion.s3_key == key)
            )
            if (count.scalar() or 0) == 0:
                try:
                    s3.delete_object(Bucket=bucket, Key=key)
                except Exception as e:
                    logger.error("Purge: S3 delete failed", extra={"key": key, "error": str(e)})
        purged += 1
    if purged:
        await db.commit()
    return purged
