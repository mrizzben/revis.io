"""Storage maintenance orchestration (T8).

Single owner of "what maintenance does" so the admin route and the lifespan
scheduler call ONE function. Failures are collected in ``errors`` rather than
raised so a partial outage does not kill the scheduler loop.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.services import file as file_service

logger = logging.getLogger(__name__)


async def run_maintenance(
    db: AsyncSession,
    abort_multipart_older_than_days: int | None = None,
) -> dict[str, Any]:
    """Abort abandoned multipart uploads and purge expired soft-deleted items.

    Returns a report with per-item error messages; the caller decides whether
    to surface them.
    """
    days = abort_multipart_older_than_days or (settings.MULTIPART_ABANDON_AFTER_SECONDS // 86400)
    s3 = file_service._get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    now = datetime.now(UTC)
    errors: list[str] = []

    multipart_cutoff = now - timedelta(days=days)
    aborted = 0
    for upload in file_service.list_abandoned_multipart_uploads(s3, bucket, multipart_cutoff):
        try:
            s3.abort_multipart_upload(
                Bucket=bucket, Key=upload["key"], UploadId=upload["upload_id"]
            )
            aborted += 1
        except Exception as e:
            errors.append(f"abort multipart {upload['upload_id']}: {e}")

    soft_delete_cutoff = now - timedelta(seconds=settings.SOFT_DELETE_RETENTION_SECONDS)
    purged = await file_service.purge_soft_deleted(db, soft_delete_cutoff)

    return {
        "aborted_multipart_uploads": aborted,
        "purged_soft_deleted_files": purged,
        "retention_window_days": days,
        "errors": errors,
    }
