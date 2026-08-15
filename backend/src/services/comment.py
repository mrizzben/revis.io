"""Comment CRUD service with threaded replies and WebSocket broadcasting."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.comment import Comment
from src.models.file import CLIENT_VISIBLE_VISIBILITIES, DesignFile, FileVersion
from src.models.project import Project
from src.models.user import User, UserRole
from src.schemas.comment import CommentCreate, CommentUpdate
from src.services import activity
from src.services.notification import send_comment_reply_notification
from src.websocket import get_manager


class CommentService:

    @staticmethod
    def to_dict(comment: Comment, version_numbers: dict[int, int] | None = None) -> dict:
        """Serialize a (relationship-loaded) comment with revision scope (T1)."""
        version_numbers = version_numbers or {}
        return {
            "id": comment.id,
            "file_id": str(comment.file_id),
            "parent_id": comment.parent_id,
            "version_id": comment.version_id,
            "scope": "revision" if comment.version_id else "all",
            "version_number": version_numbers.get(comment.version_id) if comment.version_id else None,
            "body": comment.body,
            "is_resolved": comment.is_resolved,
            "resolved_at": comment.resolved_at,
            "resolved_by": {"id": comment.resolved_by.id, "name": comment.resolved_by.name}
            if comment.resolved_by
            else None,
            "author": {
                "id": comment.author.id,
                "name": comment.author.name,
                "email": comment.author.email,
            }
            if comment.author
            else None,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
        }

    @staticmethod
    async def _user_is_architect_of_project(
        db: AsyncSession, user_id: int, project_id: int
    ) -> bool:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return False

        if project.owner_id == user_id:
            return True

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.architect:
            return False

        if user.firm_id is not None and user.firm_id == project.firm_id:
            return True

        return False

    @staticmethod
    async def _get_project_name(db: AsyncSession, project_id: int) -> str:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        return project.name if project else "Unknown Project"

    @staticmethod
    async def create_comment(
        db: AsyncSession, file_id: str, data: CommentCreate, author_id: int
    ) -> Comment:
        file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
        file_result = await db.execute(
            select(DesignFile).where(
                DesignFile.id == file_uuid,
                DesignFile.is_deleted == False,
            )
        )
        file = file_result.scalar_one_or_none()
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        author_result = await db.execute(select(User).where(User.id == author_id))
        author = author_result.scalar_one_or_none()
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Author not found"
            )

        from src.services.project import _get_project_with_access

        await _get_project_with_access(db, file.project_id, author)

        version = None
        if data.version_id is not None:
            version_result = await db.execute(
                select(FileVersion).where(FileVersion.id == data.version_id)
            )
            version = version_result.scalar_one_or_none()
            if not version or str(version.file_id) != file_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Revision not found on this file",
                )
            # Clients may only comment on revisions they were issued (T7).
            if author.role == UserRole.client and version.visibility not in CLIENT_VISIBLE_VISIBILITIES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot comment on this revision",
                )

        if data.parent_id is not None:
            parent_result = await db.execute(
                select(Comment).where(Comment.id == data.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            if not parent or str(parent.file_id) != file_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent comment not found on this file",
                )

        comment = Comment(
            file_id=file_uuid,
            author_id=author_id,
            parent_id=data.parent_id,
            version_id=data.version_id,
            body=data.body.strip(),
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        comment_result = await db.execute(
            select(Comment)
            .options(selectinload(Comment.author), selectinload(Comment.resolved_by))
            .where(Comment.id == comment.id)
        )
        comment = comment_result.scalar_one()

        # Comment applies to the item as a whole, or to one revision (T1).
        comment_is_client_visible = False
        if author.role == UserRole.client or (version is not None and version.visibility in CLIENT_VISIBLE_VISIBILITIES):
            comment_is_client_visible = True

        try:
            ws = get_manager()
            if comment_is_client_visible:
                await ws.broadcast_to_project(
                    file.project_id,
                    {
                        "type": "comment_added",
                        "file_id": str(file_id),
                        "comment_id": comment.id,
                        "project_id": file.project_id,
                    },
                )
            else:
                from src.models.project import Project, ProjectMember

                team_result = await db.execute(
                    select(ProjectMember)
                    .where(
                        ProjectMember.project_id == file.project_id,
                        ProjectMember.role == "collaborator",
                    )
                )
                team_ids = [m.user_id for m in team_result.scalars().all()]
                proj_result = await db.execute(
                    select(Project).where(Project.id == file.project_id)
                )
                owner = proj_result.scalar_one_or_none()
                if owner and owner.owner_id:
                    team_ids.append(owner.owner_id)
                await ws.broadcast_to_project_team(
                    file.project_id,
                    {
                        "type": "comment_added",
                        "file_id": str(file_id),
                        "comment_id": comment.id,
                        "project_id": file.project_id,
                    },
                    team_user_ids=team_ids,
                )
        except RuntimeError:
            pass

        await activity.record_event(
            db,
            project_id=file.project_id,
            actor_id=author_id,
            event_type="comment_created",
            entity_type="comment",
            entity_id=comment.id,
            payload={
                "file_id": str(file_id),
                "file_name": file.filename,
                "version_id": data.version_id,
            },
            visibility="client" if comment_is_client_visible else "internal",
        )

        if data.parent_id is not None:
            project_name = await CommentService._get_project_name(
                db, file.project_id
            )
            await send_comment_reply_notification(
                db=db,
                parent_comment_id=data.parent_id,
                replier_name=author.name,
                file_name=file.filename,
                project_name=project_name,
                project_id=file.project_id,
            )

        return CommentService.to_dict(comment)

    @staticmethod
    async def list_comments(db: AsyncSession, file_id: str) -> list[dict]:
        """List threaded comments with revision scope metadata (T1)."""
        file_uuid = uuid.UUID(str(file_id)) if not isinstance(file_id, uuid.UUID) else file_id
        file_result = await db.execute(
            select(DesignFile).where(
                DesignFile.id == file_uuid,
                DesignFile.is_deleted == False,
            )
        )
        if not file_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        stmt = (
            select(Comment)
            .options(selectinload(Comment.author), selectinload(Comment.resolved_by))
            .where(Comment.file_id == file_uuid)
            .order_by(Comment.created_at)
        )
        result = await db.execute(stmt)
        all_comments = result.scalars().all()

        version_ids = {c.version_id for c in all_comments if c.version_id}
        version_numbers: dict[int, int] = {}
        if version_ids:
            version_result = await db.execute(
                select(FileVersion.id, FileVersion.version_number).where(
                    FileVersion.id.in_(version_ids)
                )
            )
            version_numbers = {vid: vn for vid, vn in version_result.all()}

        def _serialize(c: Comment) -> dict:
            return {
                "id": c.id,
                "file_id": str(c.file_id),
                "parent_id": c.parent_id,
                "version_id": c.version_id,
                "scope": "revision" if c.version_id else "all",
                "version_number": version_numbers.get(c.version_id) if c.version_id else None,
                "body": c.body,
                "is_resolved": c.is_resolved,
                "resolved_at": c.resolved_at,
                "resolved_by": {
                    "id": c.resolved_by.id,
                    "name": c.resolved_by.name,
                }
                if c.resolved_by
                else None,
                "author": {
                    "id": c.author.id,
                    "name": c.author.name,
                    "email": c.author.email,
                }
                if c.author
                else None,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "replies": [],
            }

        children_map: dict[int, list[dict]] = {}
        roots: list[dict] = []
        for c in all_comments:
            item = _serialize(c)
            if c.parent_id:
                children_map.setdefault(c.parent_id, []).append(item)
            else:
                roots.append(item)

        def attach_replies(comment: dict) -> None:
            comment["replies"] = children_map.get(comment["id"], [])
            for reply in comment["replies"]:
                attach_replies(reply)

        for root in roots:
            attach_replies(root)

        return roots

    @staticmethod
    async def get_comment(db: AsyncSession, comment_id: int) -> Comment:
        result = await db.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
            )
        return comment

    @staticmethod
    async def update_comment(
        db: AsyncSession, comment_id: int, data: CommentUpdate, user_id: int
    ) -> Comment:
        comment = await CommentService.get_comment(db, comment_id)

        is_author = comment.author_id == user_id
        is_architect = await CommentService._user_is_architect_of_project(
            db, user_id, comment.file.project_id
        )

        was_resolved = comment.is_resolved

        if is_author:
            if not is_architect and data.is_resolved is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only architects can mark comments as resolved",
                )
            if data.body is not None:
                comment.body = data.body.strip()
            if is_architect and data.is_resolved is not None:
                comment.is_resolved = data.is_resolved
        elif is_architect:
            if data.body is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the author can edit the comment body",
                )
            if data.is_resolved is not None:
                comment.is_resolved = data.is_resolved
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update this comment",
            )

        # Resolution audit (T3): record who resolved/reopened and when.
        resolved_changed = (
            data.is_resolved is not None and data.is_resolved != was_resolved
        )
        if resolved_changed:
            comment.resolved_by_id = None if comment.is_resolved else None
            if comment.is_resolved:
                comment.resolved_at = datetime.now(UTC)
                comment.resolved_by_id = user_id
            else:
                comment.resolved_at = None
                comment.resolved_by_id = None
            from src.models.user import User

            actor_result = await db.execute(select(User).where(User.id == user_id))
            actor = actor_result.scalar_one_or_none()
            if actor and comment.file:
                await activity.record_event(
                    db,
                    project_id=comment.file.project_id,
                    actor_id=user_id,
                    event_type="comment_resolved" if comment.is_resolved else "comment_reopened",
                    entity_type="comment",
                    entity_id=comment.id,
                    payload={"file_id": str(comment.file_id)},
                    visibility="client",
                )

        comment.updated_at = datetime.now(UTC)
        await db.commit()
        reloaded = await db.execute(
            select(Comment)
            .options(selectinload(Comment.author), selectinload(Comment.resolved_by))
            .where(Comment.id == comment.id)
        )
        comment = reloaded.scalar_one()
        return CommentService.to_dict(comment)

    @staticmethod
    async def delete_comment(
        db: AsyncSession, comment_id: int, user_id: int
    ) -> None:
        comment = await CommentService.get_comment(db, comment_id)

        is_author = comment.author_id == user_id
        is_architect = await CommentService._user_is_architect_of_project(
            db, user_id, comment.file.project_id
        )

        if not is_author and not is_architect:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this comment",
            )

        comment.body = "[deleted]"
        await db.commit()