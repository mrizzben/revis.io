"""DesignFile and FileVersion SQLAlchemy models."""

import enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class ThumbnailStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"
    unsupported = "unsupported"


class DesignFile(Base):
    __tablename__ = "design_files"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=func.gen_random_uuid())
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_small_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_medium_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_status: Mapped[ThumbnailStatus] = mapped_column(
        Enum(ThumbnailStatus, name="thumbnail_status"),
        nullable=False,
        default=ThumbnailStatus.pending,
    )
    preview_glb_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="design_files")
    milestone: Mapped["Milestone | None"] = relationship("Milestone", back_populates="design_files")
    uploaded_by: Mapped["User"] = relationship("User")
    versions: Mapped[list["FileVersion"]] = relationship(
        "FileVersion", back_populates="file", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="file", cascade="all, delete-orphan"
    )


class FileVersion(Base):
    __tablename__ = "file_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        Uuid, ForeignKey("design_files.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    file: Mapped["DesignFile"] = relationship("DesignFile", back_populates="versions")
    uploaded_by: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("file_id", "version_number"),
    )
