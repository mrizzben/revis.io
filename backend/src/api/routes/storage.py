"""Storage lifecycle routes (T8): maintenance, usage, orphans, retention."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import DBSession, get_current_user
from src.core.config import settings
from src.models.user import User, UserRole
from src.services import file as file_service

router = APIRouter(prefix="/storage", tags=["Storage"])


async def _require_firm_or_owner(db: DBSession, user: User, project_id: int | None = None) -> None:
    """Storage admin requires an architect who is a firm admin or the project owner."""
    if user.role != UserRole.architect:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Architect access required")
    if project_id is not None:
        from src.models.project import Project

        result = await db.execute(Project.__table__.select().where(Project.id == project_id))
        project = result.mappings().first()
        if project and project["owner_id"] == user.id:
            return
        if project and project["firm_id"] and user.firm_id == project["firm_id"] and user.is_firm_admin:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this project")


@router.get("/usage")
async def storage_usage(
    db: DBSession,
    current_user: User = Depends(get_current_user),
    project_id: int | None = Query(None),
    firm_id: int | None = Query(None),
):
    """Report storage usage by project and firm (T8)."""
    if project_id is not None:
        await _require_firm_or_owner(db, current_user, project_id)
    elif firm_id is not None:
        if current_user.role != UserRole.architect or current_user.firm_id != firm_id or not current_user.is_firm_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Firm admin access required")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide project_id or firm_id",
        )
    return await file_service.report_storage_usage(
        db, project_id=project_id, firm_id=firm_id
    )


@router.get("/orphans")
async def orphaned_objects(
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List S3 objects not referenced by any revision record (T8)."""
    if current_user.role != UserRole.architect or not current_user.is_firm_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Firm admin access required")

    known_keys = await file_service.get_all_revision_keys(db)
    s3 = file_service._get_lazy_s3_client()
    try:
        orphans = file_service.list_orphaned_objects(s3, settings.S3_BUCKET, known_keys)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage service unavailable: {e}",
        ) from e
    return {"orphan_count": len(orphans), "orphans": orphans}


@router.post("/maintenance")
async def run_maintenance(
    db: DBSession,
    current_user: User = Depends(get_current_user),
    abort_multipart_older_than_days: int = Query(
        settings.MULTIPART_ABANDON_AFTER_SECONDS // 86400, ge=1
    ),
):
    """Run storage maintenance (T8):

    - abort abandoned multipart uploads older than the retention window
    - purge soft-deleted design items past the retention window
    Returns a report of what was cleaned up.
    """
    if current_user.role != UserRole.architect or not current_user.is_firm_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Firm admin access required")

    s3 = file_service._get_lazy_s3_client()
    bucket = settings.S3_BUCKET
    now = datetime.now(UTC)

    multipart_cutoff = now - timedelta(days=abort_multipart_older_than_days)
    abandoned = file_service.list_abandoned_multipart_uploads(s3, bucket, multipart_cutoff)
    aborted = 0
    for upload in abandoned:
        try:
            s3.abort_multipart_upload(Bucket=bucket, Key=upload["key"], UploadId=upload["upload_id"])
            aborted += 1
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to abort multipart upload: {e}",
            ) from e

    soft_delete_cutoff = now - timedelta(seconds=settings.SOFT_DELETE_RETENTION_SECONDS)
    purged = await file_service.purge_soft_deleted(db, soft_delete_cutoff)

    return {
        "aborted_multipart_uploads": aborted,
        "purged_soft_deleted_files": purged,
        "retention_window_days": abort_multipart_older_than_days,
    }
