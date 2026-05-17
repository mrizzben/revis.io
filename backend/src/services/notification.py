"""Notification service: email (Resend) and in-app notifications."""

from dataclasses import dataclass
from typing import Any

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.notification import Notification, NotificationType
from src.models.project import Project, ProjectMember
from src.models.user import User

resend.api_key = settings.RESEND_API_KEY


@dataclass
class EmailTemplate:
    """Simple email template with subject and HTML body."""

    subject: str
    html: str


def _base_wrapper(content: str) -> str:
    """Wrap content in a basic HTML layout."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.5; color: #1f2937; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 24px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: 500; }}
        .footer {{ margin-top: 32px; font-size: 0.875rem; color: #9ca3af; }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>"""


def send_verification_email(to_email: str, token: str) -> None:
    """Send an email verification link."""
    verify_url = f"{settings.FRONTEND_URL}/login?verify={token}"
    content = f"""
        <h2>Verify Your Email</h2>
        <p>Click the button below to verify your email address and activate your ArchiDrive account.</p>
        <p><a href="{verify_url}" class="button">Verify Email</a></p>
        <p>Or copy and paste this link:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p class="footer">This link expires in 24 hours. If you didn't create an ArchiDrive account, you can safely ignore this email.</p>
    """

    if not settings.RESEND_API_KEY or settings.RESEND_API_KEY == "re_placeholder":
        return  # Silently skip in dev without API key

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Verify your ArchiDrive email",
            "html": _base_wrapper(content),
        })
    except Exception:
        # Log but don't crash
        pass


def send_invitation_email(
    to_email: str,
    project_name: str,
    invited_by_name: str,
    token: str,
) -> None:
    """Send a project invitation email."""
    invite_url = f"{settings.FRONTEND_URL}/invitation/{token}"
    content = f"""
        <h2>You're Invited!</h2>
        <p>{invited_by_name} has invited you to collaborate on <strong>{project_name}</strong> via ArchiDrive.</p>
        <p>Click below to accept the invitation and create your account:</p>
        <p><a href="{invite_url}" class="button">Accept Invitation</a></p>
        <p>Or copy and paste this link:</p>
        <p><a href="{invite_url}">{invite_url}</a></p>
        <p class="footer">This invitation expires in 7 days.</p>
    """

    if not settings.RESEND_API_KEY or settings.RESEND_API_KEY == "re_placeholder":
        return

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": f"{invited_by_name} invited you to {project_name}",
            "html": _base_wrapper(content),
        })
    except Exception:
        pass


def send_password_reset_email(to_email: str, token: str) -> None:
    """Send a password reset email."""
    reset_url = f"{settings.FRONTEND_URL}/login?reset={token}"
    content = f"""
        <h2>Reset Your Password</h2>
        <p>Click the button below to reset your ArchiDrive password.</p>
        <p><a href="{reset_url}" class="button">Reset Password</a></p>
        <p>Or copy and paste this link:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p class="footer">This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
    """

    if not settings.RESEND_API_KEY or settings.RESEND_API_KEY == "re_placeholder":
        return

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Reset your ArchiDrive password",
            "html": _base_wrapper(content),
        })
    except Exception:
        pass


def send_file_update_notification(
    to_email: str,
    project_name: str,
    filename: str,
    project_id: int,
) -> None:
    """Notify clients that a new file was uploaded."""
    project_url = f"{settings.FRONTEND_URL}/project/{project_id}"
    content = f"""
        <h2>New File Uploaded</h2>
        <p>A new file <strong>{filename}</strong> has been uploaded to <strong>{project_name}</strong>.</p>
        <p><a href="{project_url}" class="button">View Project</a></p>
        <p class="footer">You're receiving this because you're a member of {project_name}.</p>
    """

    if not settings.RESEND_API_KEY or settings.RESEND_API_KEY == "re_placeholder":
        return

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": f"New file in {project_name}: {filename}",
            "html": _base_wrapper(content),
        })
    except Exception:
        pass


async def create_notification(
    db: AsyncSession,
    user_id: int,
    ntype: NotificationType,
    title: str,
    body: str | None = None,
    reference_id: int | None = None,
) -> Notification:
    """Create an in-app notification record."""
    notification = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        body=body,
        reference_id=reference_id,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def get_unread_notifications(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[Notification]:
    """Get unread notifications for a user."""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_notification_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int,
) -> None:
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification:
        notification.is_read = True
        await db.commit()


async def send_milestone_completed_notification(
    db: AsyncSession,
    project_id: int,
    milestone_name: str,
) -> None:
    """Notify all client members when a milestone is completed."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return

    project_name = project.name

    members_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "client",
        )
    )
    members = members_result.scalars().all()

    for member in members:
        user_result = await db.execute(
            select(User).where(User.id == member.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        project_url = f"{settings.FRONTEND_URL}/project/{project_id}"
        content = f"""
            <h2>Milestone Completed</h2>
            <p>The milestone <strong>{milestone_name}</strong> has been marked as completed in <strong>{project_name}</strong>.</p>
            <p><a href="{project_url}" class="button">View Project</a></p>
            <p class="footer">You're receiving this because you're a member of {project_name}.</p>
        """

        if settings.RESEND_API_KEY and settings.RESEND_API_KEY != "re_placeholder":
            try:
                resend.Emails.send({
                    "from": settings.EMAIL_FROM,
                    "to": user.email,
                    "subject": f"Milestone completed: {milestone_name} in {project_name}",
                    "html": _base_wrapper(content),
                })
            except Exception:
                pass

        await create_notification(
            db=db,
            user_id=user.id,
            ntype=NotificationType.milestone_completed,
            title=f"Milestone completed: {milestone_name}",
            body=f"Milestone '{milestone_name}' in {project_name} has been marked as completed.",
            reference_id=project_id,
        )


async def send_comment_reply_notification(
    db: AsyncSession,
    parent_comment_id: int,
    replier_name: str,
    file_name: str,
    project_name: str,
    project_id: int,
) -> None:
    """Notify parent comment author when someone replies to their comment."""
    from src.models.comment import Comment

    result = await db.execute(
        select(Comment).where(Comment.id == parent_comment_id)
    )
    parent = result.scalar_one_or_none()
    if not parent:
        return

    user_result = await db.execute(
        select(User).where(User.id == parent.author_id)
    )
    parent_author = user_result.scalar_one_or_none()
    if not parent_author or parent_author.name == replier_name:
        return

    project_url = f"{settings.FRONTEND_URL}/project/{project_id}"
    content = f"""
        <h2>New Reply</h2>
        <p>{replier_name} replied to your comment on <strong>{file_name}</strong> in <strong>{project_name}</strong>.</p>
        <p><a href="{project_url}" class="button">View Project</a></p>
        <p class="footer">You're receiving this because someone replied to your comment on ArchiDrive.</p>
    """

    if settings.RESEND_API_KEY and settings.RESEND_API_KEY != "re_placeholder":
        try:
            resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": parent_author.email,
                "subject": f"{replier_name} replied to your comment on {file_name}",
                "html": _base_wrapper(content),
            })
        except Exception:
            pass

    await create_notification(
        db=db,
        user_id=parent_author.id,
        ntype=NotificationType.comment_replied,
        title=f"{replier_name} replied to your comment",
        body=f"New reply from {replier_name} on {file_name} in {project_name}",
        reference_id=project_id,
    )


async def send_file_upload_notifications(
    db: AsyncSession,
    project_id: int,
    file_name: str,
    uploader_name: str,
) -> None:
    """Notify all client members of a project about a new file upload."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return

    project_name = project.name

    members_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "client",
        )
    )
    members = members_result.scalars().all()

    for member in members:
        user_result = await db.execute(
            select(User).where(User.id == member.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        send_file_update_notification(
            to_email=user.email,
            project_name=project_name,
            filename=file_name,
            project_id=project_id,
        )

        await create_notification(
            db=db,
            user_id=user.id,
            ntype=NotificationType.file_uploaded,
            title=f"New file uploaded to {project_name}",
            body=f"{uploader_name} uploaded {file_name}",
            reference_id=project_id,
        )
