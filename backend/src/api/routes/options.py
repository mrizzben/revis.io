"""Design option routes (T5): parallel design exploration without branches."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import DBSession, get_current_user
from src.models.design_option import DesignOption
from src.models.file import DesignFile
from src.models.user import User, UserRole
from src.schemas.design_option import (
    DesignOptionCreate,
    DesignOptionUpdate,
    ForkItemRequest,
)
from src.services import activity
from src.services import file as file_service
from src.services import project as project_service

router = APIRouter(tags=["Design Options"])


def _serialize(option: DesignOption, file_count: int = 0) -> dict:
    return {
        "id": option.id,
        "project_id": option.project_id,
        "name": option.name,
        "description": option.description,
        "is_current": option.is_current,
        "is_archived": option.is_archived,
        "file_count": file_count,
        "created_at": option.created_at,
        "updated_at": option.updated_at,
    }


async def _count_files(db: DBSession, option_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(DesignFile).where(
            DesignFile.design_option_id == option_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    return result.scalar() or 0


@router.get("/projects/{project_id}/options")
async def list_options(
    project_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List design options. Clients only ever see the current, non-archived option."""
    await project_service._get_project_with_access(db, project_id, current_user)

    stmt = select(DesignOption).where(DesignOption.project_id == project_id)
    if current_user.role == UserRole.client:
        stmt = stmt.where(DesignOption.is_archived.is_(False))
    stmt = stmt.order_by(DesignOption.created_at)
    result = await db.execute(stmt)
    options = list(result.scalars().all())
    return [_serialize(o, await _count_files(db, o.id)) for o in options]


@router.post("/projects/{project_id}/options", status_code=status.HTTP_201_CREATED)
async def create_option(
    project_id: int,
    data: DesignOptionCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Create a design option, e.g. 'Option A' or 'Courtyard scheme' (T5)."""
    await project_service._get_project_with_access(
        db, project_id, current_user, require_owner=True
    )
    option = DesignOption(
        project_id=project_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
    )
    db.add(option)
    await db.commit()
    await db.refresh(option)

    await activity.record_event(
        db,
        project_id=project_id,
        actor_id=current_user.id,
        event_type="option_created",
        entity_type="design_option",
        entity_id=option.id,
        payload={"name": option.name},
        visibility="internal",
    )
    return _serialize(option)


@router.patch("/options/{option_id}")
async def update_option(
    option_id: int,
    data: DesignOptionUpdate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Rename, set current/preferred, or archive a design option (T5)."""
    result = await db.execute(select(DesignOption).where(DesignOption.id == option_id))
    option = result.scalar_one_or_none()
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
    await project_service._get_project_with_access(
        db, option.project_id, current_user, require_owner=True
    )

    if data.name is not None:
        option.name = data.name.strip()
    if data.description is not None:
        option.description = data.description.strip() or None
    if data.is_current:
        # Promote: only one option may be current at a time.
        others = await db.execute(
            select(DesignOption).where(
                DesignOption.project_id == option.project_id,
                DesignOption.is_current.is_(True),
                DesignOption.id != option.id,
            )
        )
        for other in others.scalars().all():
            other.is_current = False
        option.is_current = True
        option.is_archived = False
    if data.is_archived:
        option.is_archived = True
        option.is_current = False

    option.updated_at = func.now()
    await db.commit()
    await db.refresh(option)

    await activity.record_event(
        db,
        project_id=option.project_id,
        actor_id=current_user.id,
        event_type="option_updated",
        entity_type="design_option",
        entity_id=option.id,
        payload={
            "name": option.name,
            "is_current": option.is_current,
            "is_archived": option.is_archived,
        },
        visibility="internal",
    )
    return _serialize(option, await _count_files(db, option.id))


@router.post("/options/{option_id}/fork", status_code=status.HTTP_201_CREATED)
async def fork_item(
    option_id: int,
    data: ForkItemRequest,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Fork a design item into an option, copying its revision history (T5)."""
    result = await db.execute(select(DesignOption).where(DesignOption.id == option_id))
    option = result.scalar_one_or_none()
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
    if option.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archived options cannot receive forks")

    await project_service._get_project_with_access(
        db, option.project_id, current_user, require_owner=True
    )

    source = await file_service.get_file(db, data.file_id)
    if source.project_id != option.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source file does not belong to this project",
        )

    # Copy the design item (stable identity for the option) and its revision
    # history — sharing immutable content keys (T8 dedupe; T5: no history destroyed).
    from src.models.file import FileVersion

    fork = DesignFile(
        id=uuid.uuid4(),  # fresh identity; parent_file_id records the lineage
        project_id=option.project_id,
        milestone_id=source.milestone_id,
        design_option_id=option.id,
        parent_file_id=source.id,
        uploaded_by_id=current_user.id,
        filename=source.filename,
        file_type=source.file_type,
        content_type=source.content_type,
        file_size=source.file_size,
        s3_key=source.s3_key,
        thumbnail_status=source.thumbnail_status,
        thumbnail_small_key=source.thumbnail_small_key,
        thumbnail_medium_key=source.thumbnail_medium_key,
        preview_glb_key=source.preview_glb_key,
        preview_status=source.preview_status,
    )
    db.add(fork)
    await db.flush()

    src_versions = await db.execute(
        select(FileVersion).where(FileVersion.file_id == source.id).order_by(FileVersion.version_number)
    )
    copied: list[FileVersion] = []
    for v in src_versions.scalars().all():
        nv = FileVersion(
            file_id=fork.id,
            version_number=v.version_number,
            s3_key=v.s3_key,
            file_size=v.file_size,
            content_hash=v.content_hash,
            uploaded_by_id=v.uploaded_by_id,
            revision_message=v.revision_message,
            name=v.name,
            description=v.description,
            visibility=v.visibility,
            issued_by_id=v.issued_by_id,
            issued_at=v.issued_at,
            superseded_by_id=v.superseded_by_id,
            superseded_at=v.superseded_at,
            milestone_id=v.milestone_id,
            scan_status=v.scan_status,
            mime_valid=v.mime_valid,
            restored_from_superseded=v.restored_from_superseded,
        )
        copied.append(nv)
    db.add_all(copied)
    await db.flush()
    # Point the fork's current version at its own copied revision.
    current_src = None
    if source.current_version_id:
        src_cur = await db.get(FileVersion, source.current_version_id)
        current_src = src_cur.version_number if src_cur else None
    fork_current = next(
        (v.id for v in copied if v.version_number == current_src),
        None,
    )
    if fork_current is None and copied:
        # Fall back to highest version when the source has no current version.
        fork_current = max(copied, key=lambda v: v.version_number).id
    fork.current_version_id = fork_current
    await db.commit()
    await db.refresh(fork)

    await activity.record_event(
        db,
        project_id=option.project_id,
        actor_id=current_user.id,
        event_type="item_forked",
        entity_type="design_file",
        entity_id=str(fork.id),
        payload={
            "option_id": option.id,
            "option_name": option.name,
            "source_file_id": str(source.id),
            "source_file_name": source.filename,
            "version_count": len(copied),
        },
        visibility="internal",
    )
    return await file_service.build_file_payload(db, fork, current_user)


@router.get("/options/{option_id}/files")
async def list_option_files(
    option_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List design items in an option (role-aware)."""
    result = await db.execute(
        select(DesignOption).where(DesignOption.id == option_id)
    )
    option = result.scalar_one_or_none()
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option not found")
    await project_service._get_project_with_access(db, option.project_id, current_user)

    stmt = (
        select(DesignFile)
        .options(selectinload(DesignFile.uploaded_by), selectinload(DesignFile.design_option))
        .where(
            DesignFile.design_option_id == option_id,
            DesignFile.is_deleted.is_(False),
        )
    )
    result = await db.execute(stmt)
    files = list(result.scalars().all())

    if current_user.role == UserRole.client:
        visible = []
        for f in files:
            if await file_service.list_client_versions(db, str(f.id)):
                visible.append(f)
        return [
            await file_service.build_file_payload(db, f, current_user)
            for f in visible
        ]
    return [
        await file_service.build_file_payload(db, f, current_user)
        for f in files
    ]
