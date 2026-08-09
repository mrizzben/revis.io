"""Model registry — import all models to register with Base.metadata."""

from src.models.comment import Comment
from src.models.file import DesignFile, FileVersion
from src.models.internal_note import InternalNote, Mention
from src.models.milestone import Milestone
from src.models.notification import Notification, NotificationType
from src.models.project import Invitation, Project, ProjectMember
from src.models.todo import ToDo
from src.models.user import EmailVerification, Firm, PasswordReset, User, UserRole

__all__ = [
    "Comment",
    "DesignFile",
    "EmailVerification",
    "FileVersion",
    "Firm",
    "InternalNote",
    "Invitation",
    "Mention",
    "Milestone",
    "Notification",
    "NotificationType",
    "PasswordReset",
    "Project",
    "ProjectMember",
    "ToDo",
    "User",
    "UserRole",
]
