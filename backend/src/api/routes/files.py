"""File routes: presigned upload/download URLs, multipart, revisions (T1/T2/T4/T7)."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import DBSession, get_current_user, require_role
from src.models.file import DesignFile, RevisionVisibility
from src.models.milestone import Milestone
from src.models.project import ProjectMember
from src.models.user import User, UserRole
from src.schemas.file import (
    CompareRequest,
    FileUploadUrlRequest,
    MultipartCompleteRequest,
    MultipartInitiateRequest,
    MultipartPartUrlsRequest,
    VersionMetaUpdate,
)
from src.services import activity
from src.services import file as file_service
from src.services import project as project_service
from src.services.notification import send_revision_issued_notifications
from src.websocket import get_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


async def _validate_milestone(db: DBSession, milestone_id: int | None, project_id: int) -> None:
    if milestone_id is None:
        return
    milestone_result = await db.execute(select(Milestone).where(Milestone.id == milestone_id))
    milestone = milestone_result.scalar_one_or_none()
    if not milestone or milestone.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Milestone not found in this project",
        )


async def _validate_option(db: DBSession, option_id: int | None, project_id: int) -> None:
    if option_id is None:
        return
    from src.models.design_option import DesignOption

    result = await db.execute(select(DesignOption).where(DesignOption.id == option_id))
    option = result.scalar_one_or_none()
    if not option or option.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design option not found in this project",
        )


async def _project_owner_id(db: DBSession, project_id: int) -> int | None:
    from src.models.project import Project

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    return project.owner_id if project else None


async def _resolve_upload_target(
    db: DBSession,
    current_user: User,
    request: FileUploadUrlRequest | MultipartInitiateRequest,
) -> tuple[str, str]:
    """Validate the upload request and return (s3_key, file_id).

    A new upload creates a fresh design item; passing `file_id` uploads a new
    revision of the existing item (stable identity, T1).
    """
    project = await project_service._get_project_with_access(
        db, request.project_id, current_user, require_owner=True
    )
    await _validate_milestone(db, request.milestone_id, request.project_id)
    await _validate_option(db, getattr(request, "design_option_id", None), request.project_id)

    if request.file_id:
        file = await file_service.get_file(db, request.file_id)
        if file.project_id != request.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File does not belong to this project",
            )
        return file.s3_key, str(file.id)

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
        design_option_id=getattr(request, "design_option_id", None),
    )
    return s3_key, str(file_record.id)


# ── Upload URL (Single PUT) ───────────────────────────────


@router.post("/upload-url")
async def get_upload_url(
    request: FileUploadUrlRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Get a presigned S3 upload URL for a single PUT upload (≤100MB).

    Pass `file_id` to upload a new revision of an existing design item (T1).
    """
    s3_key, file_id = await _resolve_upload_target(db, current_user, request)

    # New revision of an existing item reuses its stored key? No — fresh key,
    # immutable per revision. If target existed, get_file returned its CURRENT
    # key; generate a fresh key for the new revision instead.
    if request.file_id:
        s3_key = file_service.generate_s3_key(request.project_id, request.filename)

    url = file_service.create_presigned_upload_url(
        key=s3_key,
        content_type=request.content_type,
    )
    return {"url": url, "key": s3_key, "file_id": file_id}


# ── Multipart Upload ──────────────────────────────────────


@router.post("/multipart/initiate")
async def initiate_multipart(
    request: MultipartInitiateRequest,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Initiate a multipart S3 upload for files >100MB."""
    s3_key, file_id = await _resolve_upload_target(db, current_user, request)
    if request.file_id:
        s3_key = file_service.generate_s3_key(request.project_id, request.filename)

    upload_id = file_service.initiate_multipart_upload(
        key=s3_key,
        content_type=request.content_type,
    )
    return {"upload_id": upload_id, "key": s3_key, "file_id": file_id}


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
    result = await db.execute(select(DesignFile).where(DesignFile.s3_key == request.key))
    file_record = result.scalar_one_or_none()
    if file_record:
        file_record.thumbnail_status = file_service.ThumbnailStatus.pending
        await db.commit()
        await db.refresh(file_record)
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


# ── Upload completion → revision recording (T1/T8) ────────


@router.post("/{file_id}/upload-complete")
async def upload_complete(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
    revision_message: str | None = Query(None),
    name: str | None = Query(None),
    description: str | None = Query(None),
    milestone_id: int | None = Query(None),
    key: str | None = Query(None),
):
    """Record a completed upload as the item's next revision (T1/T8).

    Runs the trust-boundary checks (hash, MIME, malware scan, dedupe). The new
    revision is internal-only and broadcast to the team, never to clients (T7:
    issuing is an explicit action, not a side effect of upload). `key` is the
    freshly uploaded object's S3 key returned by upload-url/initiate.
    """
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )

    if milestone_id is not None:
        await _validate_milestone(db, milestone_id, file.project_id)

    version = await file_service.create_revision(
        db=db,
        file_id=file_id,
        uploaded_by_id=current_user.id,
        revision_message=revision_message,
        name=name,
        description=description,
        milestone_id=milestone_id,
        s3_key=key,
    )

    # Trigger thumbnail (and 3D preview) generation. Best-effort: a queue
    # outage must not fail an otherwise-successful upload.
    from src.services.thumbnail import enqueue_preview_job, enqueue_thumbnail_job

    try:
        await enqueue_thumbnail_job(str(file.id), version.s3_key, file.file_type)
        if file.file_type in ("ifc", "obj", "stl"):
            await enqueue_preview_job(str(file.id), version.s3_key, file.file_type)
    except Exception as exc:
        logger.warning(
            "Thumbnail enqueue failed",
            extra={"file_id": str(file.id), "error": str(exc)},
        )

    # Team-only broadcast: internal drafts must not reach clients (T7).
    team_ids = [
        m.user_id
        for m in (
            await db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == file.project_id,
                    ProjectMember.role == "collaborator",
                )
            )
        )
        .scalars()
        .all()
    ]
    owner_id = await _project_owner_id(db, file.project_id)
    if owner_id:
        team_ids.append(owner_id)

    try:
        ws = get_manager()
        await ws.broadcast_to_project_team(
            file.project_id,
            {
                "type": "revision_created",
                "file_id": str(file.id),
                "version_number": version.version_number,
                "filename": file.filename,
            },
            team_user_ids=list(set(team_ids)),
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_created",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
            "size": version.file_size,
            "hash": version.content_hash,
        },
        visibility="internal",
    )

    return {
        "message": "Processing started",
        "file_id": str(file.id),
        "version_number": version.version_number,
    }


# ── Project file listing (role-aware, T7) ─────────────────


async def _list_files_route(
    project_id: int,
    db: DBSession,
    current_user: User,
    milestone_id: int | None = None,
):
    """List project files with revision visibility applied per role."""
    await project_service._get_project_with_access(db, project_id, current_user)

    query = (
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by), selectinload(DesignFile.design_option))
        .where(DesignFile.project_id == project_id, DesignFile.is_deleted.is_(False))
    )
    if milestone_id is not None:
        query = query.where(DesignFile.milestone_id == milestone_id)
    result = await db.execute(query)
    files = list(result.scalars().all())

    if current_user.role == UserRole.client:
        # Clients see only items with an issued revision (T7).
        visible = []
        for f in files:
            versions = await file_service.list_client_versions(db, str(f.id))
            if versions:
                visible.append((f, versions))
        return [await file_service.build_file_payload(db, f, current_user) for f, _ in visible]

    return [await file_service.build_file_payload(db, f, current_user) for f in files]


# ── File Management ───────────────────────────────────────


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get file details with role-aware revision info."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    # T7: a client must not even infer the existence of an un-issued item.
    if current_user.role == UserRole.client:
        versions = await file_service.list_client_versions(db, str(file.id))
        if not versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return await file_service.build_file_payload(db, file, current_user)


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

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="file_deleted",
        entity_type="design_file",
        entity_id=str(file.id),
        payload={"file_name": file.filename},
        visibility="client",
    )
    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {"type": "file_deleted", "file_id": str(file.id)},
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass


@router.get("/{file_id}/download")
async def get_download_url(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    return_url: bool = Query(False),
    inline: bool = Query(False),
):
    """Get a presigned download URL for a file's current revision.

    Clients always download the latest revision they were issued (T7).
    """
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    if current_user.role == UserRole.client:
        versions = await file_service.list_client_versions(db, str(file.id))
        version = file_service.effective_client_version(versions)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No issued revision available"
            )
    else:
        version = None
        if file.current_version_id:
            from src.models.file import FileVersion

            vresult = await db.execute(
                select(FileVersion).where(FileVersion.id == file.current_version_id)
            )
            version = vresult.scalar_one_or_none()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No revision available"
            )

    url = file_service.create_presigned_download_url(
        key=version.s3_key,
        filename=None if inline else file.filename,
        content_type=file.content_type,
    )
    if return_url:
        return {"url": url}
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
        await _validate_milestone(db, milestone_id, file.project_id)

    file.milestone_id = milestone_id
    file.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(file)

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="milestone_changed",
        entity_type="design_file",
        entity_id=str(file.id),
        payload={"file_name": file.filename, "milestone_id": milestone_id},
        visibility="internal",
    )
    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {"type": "file_updated", "file_id": str(file.id), "milestone_id": file.milestone_id},
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass

    return {"id": str(file.id), "milestone_id": file.milestone_id}


@router.get("/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    size: str = Query("small", pattern="^(small|medium)$"),
    return_url: bool = Query(False),
):
    """Get a thumbnail URL, either as JSON or a redirect for direct navigation."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    # Clients may not see thumbnails of un-issued items (T7).
    if current_user.role == UserRole.client:
        versions = await file_service.list_client_versions(db, str(file.id))
        if not versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    key = file.thumbnail_small_key if size == "small" else file.thumbnail_medium_key
    if key:
        url = file_service.get_thumbnail_presigned_url(key)
    elif file.file_type in {"png", "jpg", "jpeg", "webp"}:
        # Keep image uploads previewable while the optional ARQ worker is
        # stopped or catching up. The original image is a valid thumbnail.
        url = file_service.create_presigned_download_url(
            key=file.s3_key,
            content_type=file.content_type,
        )
    else:
        url = None
    if not url:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    # Browsers cannot expose a cross-origin redirect target to Axios/XHR unless
    # the object store also permits that request. Return the URL as JSON so the
    # frontend can assign it directly to <img src>, which does not require CORS.
    if return_url:
        return {"url": url}
    return RedirectResponse(url=url, status_code=302)


@router.get("/{file_id}/preview")
async def get_preview(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get a 3D preview URL (redirect to presigned S3 URL for glTF/GLB)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    if current_user.role == UserRole.client:
        versions = await file_service.list_client_versions(db, str(file.id))
        if not versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    if not file.preview_glb_key:
        raise HTTPException(status_code=404, detail="Preview not available")

    url = file_service.get_thumbnail_presigned_url(file.preview_glb_key)
    if not url:
        raise HTTPException(status_code=404, detail="Preview not available")

    return RedirectResponse(url=url, status_code=302)


# ── Revision endpoints (T1/T2/T7) ─────────────────────────


async def _get_version_or_404(db: DBSession, file_id: str, version_number: int):
    version = await file_service.get_version(db, file_id, version_number)
    return version


def _version_payload(version) -> dict:
    return file_service.build_version_payload(
        version,
        current_version_id=version.file.current_version_id if version.file else None,
    )


@router.get("/{file_id}/versions")
async def list_versions(
    file_id: str,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
):
    """List revisions (role-aware: clients see only issued history)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    if current_user.role == UserRole.client:
        versions = await file_service.list_client_versions(db, str(file.id))
    else:
        versions = await file_service.list_versions(
            db, str(file.id), include_archived=include_archived
        )

    current_id = file.current_version_id
    return [
        file_service.build_version_payload(v, current_version_id=current_id, with_download_url=True)
        for v in versions
    ]


@router.get("/{file_id}/versions/{version_number}")
async def get_version_detail(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Get one revision's detail + download URL (role-checked)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    version = await file_service.get_version(db, str(file.id), version_number)
    if current_user.role == UserRole.client and version.visibility not in (
        RevisionVisibility.client_issued,
        RevisionVisibility.superseded,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    return file_service.build_version_payload(version, with_download_url=True)


@router.get("/{file_id}/versions/{version_number}/download")
async def download_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Download a specific revision (role-checked, T1)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)
    version = await file_service.get_version(db, str(file.id), version_number)

    if current_user.role == UserRole.client and version.visibility not in (
        RevisionVisibility.client_issued,
        RevisionVisibility.superseded,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    url = file_service.create_presigned_download_url(
        key=version.s3_key,
        filename=file.filename,
        content_type=file.content_type,
    )
    return RedirectResponse(url=url, status_code=302)


@router.patch("/{file_id}/versions/{version_number}")
async def update_version_meta(
    file_id: str,
    version_number: int,
    data: VersionMetaUpdate,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Rename a checkpoint, attach an issue note, associate a milestone (T2)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    if data.milestone_id is not None:
        await _validate_milestone(db, data.milestone_id, file.project_id)

    version = await file_service.update_version_meta(
        db,
        str(file.id),
        version_number,
        name=data.name,
        description=data.description,
        milestone_id=data.milestone_id,
        revision_message=data.revision_message,
    )
    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_updated",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
        },
        visibility="internal",
    )
    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/restore")
async def restore_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Restore a prior revision as current without deleting history (T1)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.restore_version(db, str(file.id), version_number, current_user)

    client_visible = version.visibility in (
        RevisionVisibility.client_issued,
        RevisionVisibility.superseded,
    )
    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_restored",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
        },
        visibility="client" if client_visible else "internal",
    )
    try:
        ws = get_manager()
        msg = {
            "type": "revision_restored",
            "file_id": str(file.id),
            "version_number": version.version_number,
        }
        if client_visible:
            await ws.broadcast_to_project(file.project_id, msg, exclude_user_id=current_user.id)
        else:
            from src.models.project import Project

            proj = (
                await db.execute(select(Project).where(Project.id == file.project_id))
            ).scalar_one_or_none()
            team_ids = [
                m.user_id
                for m in (
                    await db.execute(
                        select(ProjectMember).where(
                            ProjectMember.project_id == file.project_id,
                            ProjectMember.role == "collaborator",
                        )
                    )
                )
                .scalars()
                .all()
            ]
            if proj:
                team_ids.append(proj.owner_id)
            await ws.broadcast_to_project_team(
                file.project_id,
                msg,
                team_user_ids=list(set(team_ids)),
                exclude_user_id=current_user.id,
            )
    except RuntimeError:
        pass

    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/issue")
async def issue_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Explicitly issue a revision to the client (T2/T7)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.issue_version(db, str(file.id), version_number, current_user)

    await send_revision_issued_notifications(
        db, file.project_id, file.filename, version.version_number, current_user.name
    )
    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_issued",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
            "issued_at": version.issued_at.isoformat() if version.issued_at else None,
        },
        visibility="client",
    )
    try:
        ws = get_manager()
        await ws.broadcast_to_project(
            file.project_id,
            {
                "type": "revision_issued",
                "file_id": str(file.id),
                "version_number": version.version_number,
                "filename": file.filename,
            },
            exclude_user_id=current_user.id,
        )
    except RuntimeError:
        pass

    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/supersede")
async def supersede_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Mark a revision superseded without deleting it (T2)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.supersede_version(db, str(file.id), version_number, current_user)

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_superseded",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
        },
        visibility="client",
    )
    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/archive")
async def archive_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Archive a revision: hidden from normal views, retained for audit (T2/T7)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.archive_version(db, str(file.id), version_number)

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_archived",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
        },
        visibility="internal",
    )
    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/review")
async def set_review_state(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
    in_review: bool = Body(..., embed=True),
):
    """Move a draft between internal and internal-review state (T2)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.set_review_state(db, str(file.id), version_number, in_review)

    await activity.record_event(
        db,
        project_id=file.project_id,
        actor_id=current_user.id,
        event_type="revision_updated",
        entity_type="file_version",
        entity_id=version.id,
        payload={
            "file_id": str(file.id),
            "file_name": file.filename,
            "version_number": version.version_number,
        },
        visibility="internal",
    )
    return file_service.build_version_payload(version)


@router.post("/{file_id}/versions/{version_number}/scan")
async def rescan_version(
    file_id: str,
    version_number: int,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Re-run the malware scan for a revision (T8)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(
        db, file.project_id, current_user, require_owner=True
    )
    version = await file_service.get_version(db, str(file.id), version_number)

    s3 = file_service._get_lazy_s3_client()
    version.scan_status = file_service.scan_object_with_clamd(
        s3, settings_bucket := file_service.settings.S3_BUCKET, version.s3_key, version.file_size
    )
    await db.commit()
    await db.refresh(version)
    return {"version_number": version.version_number, "scan_status": version.scan_status.value}


# ── Comparison (T4) ───────────────────────────────────────


@router.post("/{file_id}/compare")
async def compare_versions(
    file_id: str,
    request: CompareRequest,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Compare two revisions of a design item (T4)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    from_version = await file_service.get_version(db, str(file.id), request.from_version)
    to_version = await file_service.get_version(db, str(file.id), request.to_version)

    if current_user.role == UserRole.client:
        allowed = (RevisionVisibility.client_issued, RevisionVisibility.superseded)
        if from_version.visibility not in allowed or to_version.visibility not in allowed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    return file_service.build_comparison_payload(file, from_version, to_version)
