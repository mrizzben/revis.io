"""Milestone CRUD service with WebSocket broadcasting."""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.file import DesignFile
from src.models.milestone import Milestone
from src.models.project import Project
from src.models.user import User, UserRole
from src.schemas.milestone import MilestoneCreate, MilestoneUpdate
from src.services.notification import send_milestone_completed_notification
from src.websocket import get_manager

logger = logging.getLogger(__name__)


class MilestoneService:
    @staticmethod
    async def _validate_architect_access(db: AsyncSession, project_id: int, user: User) -> Project:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        if project.owner_id == user.id or user.role == UserRole.admin:
            return project

        if user.role.value != "architect":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Architect access required",
            )

        if user.firm_id is not None and user.firm_id == project.firm_id:
            return project

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Architect access required",
        )

    @staticmethod
    async def create_milestone(
        db: AsyncSession, project_id: int, data: MilestoneCreate, user: User
    ) -> Milestone:
        project = await MilestoneService._validate_architect_access(db, project_id, user)

        if data.position is None:
            max_result = await db.execute(
                select(func.coalesce(func.max(Milestone.position), -1)).where(
                    Milestone.project_id == project_id
                )
            )
            position = (max_result.scalar() or 0) + 1
        else:
            position = data.position

        milestone = Milestone(
            project_id=project_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            position=position,
        )
        db.add(milestone)
        await db.commit()
        await db.refresh(milestone)

        logger.info(
            "Milestone created",
            extra={"milestone_id": milestone.id, "project_id": project_id},
        )

        try:
            ws = get_manager()
            await ws.broadcast_to_project(
                project_id,
                {
                    "type": "milestone_created",
                    "milestone_id": milestone.id,
                    "project_id": project_id,
                    "name": milestone.name,
                },
            )
        except RuntimeError:
            pass

        return milestone

    @staticmethod
    async def list_milestones(db: AsyncSession, project_id: int) -> list[Milestone]:
        stmt = (
            select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.position)
        )
        result = await db.execute(stmt)
        milestones = list(result.scalars().all())

        for m in milestones:
            count_stmt = (
                select(func.count())
                .select_from(DesignFile)
                .where(
                    DesignFile.milestone_id == m.id,
                    DesignFile.is_deleted == False,
                )
            )
            count_result = await db.execute(count_stmt)
            m.file_count = count_result.scalar() or 0

        return milestones

    @staticmethod
    async def get_milestone(db: AsyncSession, milestone_id: int) -> Milestone:
        result = await db.execute(select(Milestone).where(Milestone.id == milestone_id))
        milestone = result.scalar_one_or_none()
        if not milestone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Milestone not found",
            )
        return milestone

    @staticmethod
    async def update_milestone(
        db: AsyncSession,
        milestone_id: int,
        data: MilestoneUpdate,
        user: User,
    ) -> Milestone:
        milestone = await MilestoneService.get_milestone(db, milestone_id)
        await MilestoneService._validate_architect_access(db, milestone.project_id, user)

        was_completed = milestone.is_completed
        is_completing = False

        if data.name is not None:
            milestone.name = data.name.strip()
        if data.description is not None:
            milestone.description = data.description.strip() if data.description else None
        if data.position is not None:
            milestone.position = data.position
        if data.is_completed is not None:
            if data.is_completed and not was_completed:
                milestone.is_completed = True
                milestone.completed_at = datetime.now(UTC)
                is_completing = True
            elif not data.is_completed and was_completed:
                milestone.is_completed = False
                milestone.completed_at = None

        milestone.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(milestone)

        try:
            ws = get_manager()
            event_type = "milestone_completed" if is_completing else "milestone_updated"
            await ws.broadcast_to_project(
                milestone.project_id,
                {
                    "type": event_type,
                    "milestone_id": milestone.id,
                    "project_id": milestone.project_id,
                    "name": milestone.name,
                },
            )
        except RuntimeError:
            pass

        if is_completing:
            await send_milestone_completed_notification(db, milestone.project_id, milestone.name)
            logger.info(
                "Milestone completed",
                extra={"milestone_id": milestone.id, "project_id": milestone.project_id},
            )

        return milestone

    @staticmethod
    async def delete_milestone(db: AsyncSession, milestone_id: int, user: User) -> None:
        milestone = await MilestoneService.get_milestone(db, milestone_id)
        await MilestoneService._validate_architect_access(db, milestone.project_id, user)
        await db.delete(milestone)
        await db.commit()
