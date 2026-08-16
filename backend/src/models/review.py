"""Review model — explicit design review workflow (T3)."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class ReviewStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(
        Uuid, ForeignKey("design_files.id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("file_versions.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status", native_enum=False, length=24),
        nullable=False,
        default=ReviewStatus.draft,
    )
    is_client_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    file: Mapped["DesignFile"] = relationship("DesignFile", back_populates="reviews")
    revision: Mapped["FileVersion | None"] = relationship("FileVersion")
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_id])
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewer_id])
    decided_by: Mapped["User | None"] = relationship("User", foreign_keys=[decided_by_id])
