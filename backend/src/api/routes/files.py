"""File routes: presigned upload/download URLs, multipart, file management."""

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from src.api.dependencies import DBSession, get_current_user, require_role
from src.models.file import DesignFile
from src.models.milestone import Milestone
from src.models.user import User
from src.schemas.file import (
    FileUploadUrlRequest,
    MultipartCompleteRequest,
    MultipartInitiateRequest,
    MultipartPartUrlsRequest,
)
from src.services import file as file_service
from src.services import project as project_service
from src.services.notification import send_file_upload_notifications
from src.websocket import get_manager

router = APIRouter(prefix="/files", tags=["Files"])


# ── Project Files Listing ─────────────────────────────────

# This route is scoped to projects but lives in files for code proximity
# It's registered at /api/projects/{project_id}/files
# We'll handle this in the router aggregation


# ── Upload URL (Single PUT) ───────────────────────────────

@router.post("/upload-url")
async def get_upload_url(
    request: FileUploadUrlRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Get a presigned S3 upload URL for a single PUT upload (≤100MB)."""
    # Validate project access
    project = await project_service._get_project_with_access(
        db, request.project_id, current_user, require_owner=True
    )

    # Validate milestone belongs to this project
    if request.milestone_id is not None:
        milestone_result = await db.execute(
            select(Milestone).where(Milestone.id == request.milestone_id)
        )
        milestone = milestone_result.scalar_one_or_none()
        if not milestone or milestone.project_id != request.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone not found in this project",
            )

    # Validate file metadata
    ext = file_service.validate_file_upload(
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
    )

    # Generate S3 key
    s3_key = file_service.generate_s3_key(request.project_id, request.filename)

    # Create file record
    file_record = await file_service.create_file_record(
        db=db,
        project_id=request.project_id,
        uploaded_by_id=current_user.id,
        filename=request.filename,
        file_type=ext,
        content_type=request.content_type,
        file_size=request.file_size,
        s3_key=s3_key,
        milestone_id=request.milestone_id,
    )

    # Generate presigned URL
    url = file_service.create_presigned_upload_url(
        key=s3_key,
        content_type=request.content_type,
    )

    return {
        "url": url,
        "key": s3_key,
        "file_id": str(file_record.id),
    }


# ── Multipart Upload ──────────────────────────────────────

@router.post("/multipart/initiate")
async def initiate_multipart(
    request: MultipartInitiateRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Initiate a multipart S3 upload for files >100MB."""
    project = await project_service._get_project_with_access(
        db, request.project_id, current_user, require_owner=True
    )

    # Validate milestone belongs to this project
    if request.milestone_id is not None:
        milestone_result = await db.execute(
            select(Milestone).where(Milestone.id == request.milestone_id)
        )
        milestone = milestone_result.scalar_one_or_none()
        if not milestone or milestone.project_id != request.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone not found in this project",
            )

    ext = file_service.validate_file_upload(
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
    )

    s3_key = file_service.generate_s3_key(request.project_id, request.filename)

    file_record = await file_service.create_file_record(
        db=db,
        project_id=request.project_id,
        uploaded_by_id=current_user.id,
        filename=request.filename,
        file_type=ext,
        content_type=request.content_type,
        file_size=request.file_size,
        s3_key=s3_key,
        milestone_id=request.milestone_id,
    )

    upload_id = file_service.initiate_multipart_upload(
        key=s3_key,
        content_type=request.content_type,
    )

    return {
        "upload_id": upload_id,
        "key": s3_key,
        "file_id": str(file_record.id),
    }


@router.post("/multipart/{upload_id}/part-urls")
async def get_part_urls(
    upload_id: str,
    request: MultipartPartUrlsRequest,
    current_user: User = Depends(require_role("architect")),
):
    """Get presigned URLs for multipart upload parts."""
    urls = file_service.create_multipart_part_urls(
        key=request.key,
        upload_id=upload_id,
        part_numbers=request.part_numbers,
    )
    return {"urls": urls}


@router.post("/multipart/{upload_id}/complete")
async def complete_multipart(
    upload_id: str,
    request: MultipartCompleteRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Complete a multipart upload."""
    file_service.complete_multipart_upload(
        key=request.key,
        upload_id=upload_id,
        parts=request.parts,
    )

    result = await db.execute(
        select(DesignFile).where(DesignFile.s3_key == request.key)
    )
    file_record = result.scalar_one_or_none()
    if file_record:
        file_record.thumbnail_status = file_service.ThumbnailStatus.pending
        await db.commit()
        await db.refresh(file_record)

        try:
            ws = get_manager()
            await ws.broadcast_to_project(
                file_record.project_id,
                {
                    "type": "file_uploaded",
                    "file_id": str(file_record.id),
                    "filename": file_record.filename,
                },
                exclude_user_id=current_user.id,
            )
        except RuntimeError:
            pass

        await send_file_upload_notifications(
            db=db,
            project_id=file_record.project_id,
            file_name=file_record.filename,
            uploader_name=current_user.name,
        )

    return {"message": "Upload completed"}


@router.post("/multipart/{upload_id}/abort")
async def abort_multipart(
    upload_id: str,
    request: MultipartCompleteRequest,  # Reuse for key field
    current_user: User = Depends(require_role("architect")),
):
    """Abort an incomplete multipart upload."""
    file_service.abort_multipart_upload(
        key=request.key,
        upload_id=upload_id,
    )
    return {"message": "Upload aborted"}


# ── File Management ───────────────────────────────────────

@router.get("/{file_id}")
async def get_file(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get file details."""
    file = await file_service.get_file(db, file_id)
    # Verify project access
    await project_service._get_project_with_access(db, file.project_id, current_user)

    return {
        "id": str(file.id),
        "project_id": file.project_id,
        "milestone_id": file.milestone_id,
        "filename": file.filename,
        "file_type": file.file_type,
        "content_type": file.content_type,
        "file_size": file.file_size,
        "thumbnail_status": file.thumbnail_status.value,
        "preview_status": file.preview_status,
        "is_deleted": file.is_deleted,
        "version_number": 1,
        "comment_count": 0,
        "uploaded_by": {
            "id": file.uploaded_by.id,
            "email": file.uploaded_by.email,
            "name": file.uploaded_by.name,
            "role": file.uploaded_by.role.value,
            "firm_id": file.uploaded_by.firm_id,
            "is_firm_admin": file.uploaded_by.is_firm_admin,
            "is_verified": file.uploaded_by.is_verified,
            "created_at": file.uploaded_by.created_at.isoformat() if file.uploaded_by.created_at else None,
        } if file.uploaded_by else None,
        "created_at": file.created_at,
        "updated_at": file.updated_at,
    }


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Soft-delete a file (architect only)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)
    await file_service.soft_delete_file(db, file_id)

    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {
                "type": "file_deleted",
                "file_id": str(file.id),
            },
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass


@router.get("/{file_id}/download")
async def get_download_url(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get a presigned download URL for a file."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    url = file_service.create_presigned_download_url(
        key=file.s3_key,
        filename=file.filename,
        content_type=file.content_type,
    )
    return RedirectResponse(url=url, status_code=302)


@router.patch("/{file_id}")
async def update_file_milestone(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
    milestone_id: int | None = Body(None, embed=True),
):
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    if milestone_id is not None:
        milestone_result = await db.execute(
            select(Milestone).where(Milestone.id == milestone_id)
        )
        milestone = milestone_result.scalar_one_or_none()
        if not milestone or milestone.project_id != file.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone not found in this project",
            )

    file.milestone_id = milestone_id
    file.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(file)

    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {
                "type": "file_updated",
                "file_id": str(file.id),
                "milestone_id": file.milestone_id,
            },
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass

    return {
        "id": str(file.id),
        "milestone_id": file.milestone_id,
        "updated_at": file.updated_at.isoformat(),
    }


@router.get("/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    size: str = Query("small", pattern="^(small|medium)$"),
):
    """Get a thumbnail URL (redirect-style response)."""
    from fastapi.responses import RedirectResponse

    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    key = file.thumbnail_small_key if size == "small" else file.thumbnail_medium_key
    if not key:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    url = file_service.get_thumbnail_presigned_url(key)
    if not url:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return RedirectResponse(url=url, status_code=302)


@router.get("/{file_id}/preview")
async def get_preview(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get a 3D preview URL (redirect to presigned S3 URL for glTF/GLB)."""
    from fastapi.responses import RedirectResponse

    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    if not file.preview_glb_key:
        raise HTTPException(status_code=404, detail="Preview not available")

    url = file_service.get_thumbnail_presigned_url(file.preview_glb_key)
    if not url:
        raise HTTPException(status_code=404, detail="Preview not available")

    return RedirectResponse(url=url, status_code=302)


@router.post("/{file_id}/upload-complete")
async def upload_complete(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
    milestone_id: int | None = Query(None),
):
    """Callback after S3 upload completes — triggers thumbnail generation."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    # Validate and apply milestone_id if provided
    if milestone_id is not None:
        milestone_result = await db.execute(
            select(Milestone).where(Milestone.id == milestone_id)
        )
        milestone = milestone_result.scalar_one_or_none()
        if not milestone or milestone.project_id != file.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone not found in this project",
            )
        file.milestone_id = milestone_id

    await file_service.complete_file_upload(db, file_id)

    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {
                "type": "file_uploaded",
                "file_id": str(file.id),
                "filename": file.filename,
            },
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass

    await send_file_upload_notifications(
        db=db,
        project_id=file.project_id,
        file_name=file.filename,
        uploader_name=current_user.name,
    )

    return {"message": "Processing started"}