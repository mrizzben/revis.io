"""Comment CRUD service with threaded replies and WebSocket broadcasting."""

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.comment import Comment
from src.models.file import DesignFile
from src.models.project import Project
from src.models.user import User, UserRole
from src.schemas.comment import CommentCreate, CommentUpdate
from src.services.notification import send_comment_reply_notification
from src.websocket import get_manager


class CommentService:

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
        file_result = await db.execute(
            select(DesignFile).where(
                DesignFile.id == file_id,
                DesignFile.is_deleted == False,
            )
        )
        file = file_result.scalar_one_or_none()
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
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

        author_result = await db.execute(
            select(User).where(User.id == author_id)
        )
        author = author_result.scalar_one_or_none()
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Author not found"
            )

        from src.services.project import _get_project_with_access

        await _get_project_with_access(db, file.project_id, author)

        comment = Comment(
            file_id=file_id,
            author_id=author_id,
            parent_id=data.parent_id,
            body=data.body.strip(),
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        comment_result = await db.execute(
            select(Comment).where(Comment.id == comment.id)
        )
        comment = comment_result.scalar_one()

        try:
            ws = get_manager()
            await ws.broadcast_to_project(
                file.project_id,
                {
                    "type": "comment_added",
                    "file_id": str(file_id),
                    "comment_id": comment.id,
                    "project_id": file.project_id,
                },
            )
        except RuntimeError:
            pass

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

        return comment

    @staticmethod
    async def list_comments(db: AsyncSession, file_id: str) -> list[Comment]:
        file_result = await db.execute(
            select(DesignFile).where(
                DesignFile.id == file_id,
                DesignFile.is_deleted == False,
            )
        )
        if not file_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        stmt = (
            select(Comment)
            .where(Comment.file_id == file_id)
            .order_by(Comment.created_at)
        )
        result = await db.execute(stmt)
        all_comments = result.scalars().all()

        children_map: dict[int, list[Comment]] = {}
        roots: list[Comment] = []
        for c in all_comments:
            if c.parent_id:
                children_map.setdefault(c.parent_id, []).append(c)
            else:
                roots.append(c)

        def attach_replies(comment: Comment, depth: int = 0) -> None:
            comment.replies = children_map.get(comment.id, [])  # type: ignore[attr-defined]
            for reply in comment.replies:
                attach_replies(reply, depth + 1)

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

        from datetime import datetime, timezone

        comment.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(comment)
        return comment

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