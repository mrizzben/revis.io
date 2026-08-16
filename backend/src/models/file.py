"""DesignFile and FileVersion SQLAlchemy models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.comment import Comment
    from src.models.design_option import DesignOption
    from src.models.milestone import Milestone
    from src.models.project import Project
    from src.models.review import Review
    from src.models.user import User


class ThumbnailStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"
    unsupported = "unsupported"


class ScanStatus(str, enum.Enum):
    """Malware scan lifecycle for a revision's object (T8)."""

    pending = "pending"
    clean = "clean"
    infected = "infected"
    error = "error"
    skipped = "skipped"


class RevisionVisibility(str, enum.Enum):
    """Who may see a revision (T7).

    internal      → owner + collaborators only
    review        → internal team (revision in internal review)
    client_issued → authorized clients (explicit issue action)
    superseded    → previously issued, replaced by a newer issue
    archived      → hidden from normal views, retained for audit
    """

    internal = "internal"
    review = "review"
    client_issued = "client_issued"
    superseded = "superseded"
    archived = "archived"


# Visibility levels that a client may ever see (issued history).
CLIENT_VISIBLE_VISIBILITIES = (
    RevisionVisibility.client_issued,
    RevisionVisibility.superseded,
)


class DesignFile(Base):
    __tablename__ = "design_files"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=func.gen_random_uuid())
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    design_option_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("design_options.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    parent_file_id: Mapped[str | None] = mapped_column(Uuid, nullable=True)
    uploaded_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    current_version_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("file_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="design_files")
    milestone: Mapped["Milestone | None"] = relationship("Milestone", back_populates="design_files")
    design_option: Mapped["DesignOption | None"] = relationship(
        "DesignOption", back_populates="design_files", foreign_keys=[design_option_id]
    )
    uploaded_by: Mapped["User"] = relationship("User")
    versions: Mapped[list["FileVersion"]] = relationship(
        "FileVersion",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FileVersion.version_number",
        foreign_keys="FileVersion.file_id",
    )
    current_version: Mapped["FileVersion | None"] = relationship(
        "FileVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="file", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="file", cascade="all, delete-orphan"
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
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    revision_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[RevisionVisibility] = mapped_column(
        Enum(RevisionVisibility, name="revision_visibility", native_enum=False, length=20),
        nullable=False,
        default=RevisionVisibility.internal,
    )
    issued_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    milestone_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    scan_status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status", native_enum=False, length=20),
        nullable=False,
        default=ScanStatus.pending,
    )
    mime_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    restored_from_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    file: Mapped["DesignFile"] = relationship(
        "DesignFile", back_populates="versions", foreign_keys=[file_id]
    )
    uploaded_by: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_id])
    issued_by: Mapped["User | None"] = relationship("User", foreign_keys=[issued_by_id])
    superseded_by: Mapped["User | None"] = relationship("User", foreign_keys=[superseded_by_id])
    milestone: Mapped["Milestone | None"] = relationship("Milestone")
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="version", foreign_keys="Comment.version_id"
    )

    __table_args__ = (UniqueConstraint("file_id", "version_number"),)
