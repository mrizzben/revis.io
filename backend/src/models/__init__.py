"""Model registry — import all models to register with Base.metadata."""

from src.models.activity import ActivityEvent
from src.models.comment import Comment
from src.models.design_option import DesignOption
from src.models.file import DesignFile, FileVersion, RevisionVisibility, ScanStatus
from src.models.internal_note import InternalNote, Mention
from src.models.milestone import Milestone
from src.models.notification import Notification, NotificationType
from src.models.project import Invitation, Project, ProjectMember
from src.models.review import Review, ReviewStatus
from src.models.todo import ToDo
from src.models.user import EmailVerification, Firm, PasswordReset, User, UserRole

__all__ = [
    "ActivityEvent",
    "Comment",
    "DesignFile",
    "DesignOption",
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
    "Review",
    "ReviewStatus",
    "RevisionVisibility",
    "ScanStatus",
    "ToDo",
    "User",
    "UserRole",
]
