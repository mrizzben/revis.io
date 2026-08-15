"""Comment SQLAlchemy model with threaded replies and revision scoping."""

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        Uuid, ForeignKey("design_files.id", ondelete="CASCADE"), nullable=False
    )
    # Null → applies to all revisions of the item; set → applies to one revision.
    version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("file_versions.id", ondelete="SET NULL"), nullable=True
    )
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    file: Mapped["DesignFile"] = relationship("DesignFile", back_populates="comments")
    version: Mapped["FileVersion | None"] = relationship(
        "FileVersion", back_populates="comments", foreign_keys=[version_id]
    )
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    resolved_by: Mapped["User | None"] = relationship("User", foreign_keys=[resolved_by_id])
    parent: Mapped["Comment | None"] = relationship(
        "Comment", remote_side=[id], back_populates="replies"
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="parent", cascade="all, delete-orphan"
    )
