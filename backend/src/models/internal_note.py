"""Internal note model with threaded replies and @mentions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class InternalNote(Base):
    __tablename__ = "internal_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("internal_notes.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    author = relationship("User")
    parent: Mapped["InternalNote | None"] = relationship(
        "InternalNote", remote_side=[id], back_populates="replies"
    )
    replies: Mapped[list["InternalNote"]] = relationship(
        "InternalNote", back_populates="parent", order_by="InternalNote.created_at"
    )
    mentions: Mapped[list["Mention"]] = relationship(
        "Mention", back_populates="note", cascade="all, delete-orphan"
    )


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("internal_notes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    note: Mapped["InternalNote"] = relationship("InternalNote", back_populates="mentions")
    user = relationship("User")

    __table_args__ = (UniqueConstraint("note_id", "user_id"),)
