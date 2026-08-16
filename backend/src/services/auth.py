"""Authentication service: registration, login, token management, password reset."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import (
    create_access_token,
    create_refresh_token,
    create_url_safe_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.models.project import Invitation, ProjectMember
from src.models.user import EmailVerification, PasswordReset, User, UserRole
from src.services.notification import (
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    role: str,
    invitation_token: str | None = None,
) -> User:
    """Register a new user. Clients must provide a valid invitation token."""

    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # The guest-*@revis.io namespace is reserved for per-project anonymous
    # client identities (secure-link access, no sign-up).
    if email.lower().endswith("@revis.io") and email.lower().startswith("guest-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is reserved",
        )

    user_role = UserRole(role)

    # Trim name
    name = name.strip()

    # Create user
    user = User(
        email=email,
        name=name,
        hashed_password=hash_password(password),
        role=user_role,
        is_verified=False,
    )

    # Handle client registration via invitation
    if user_role == UserRole.client:
        if not invitation_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client registration requires an invitation token",
            )
        await _validate_and_consume_invitation(db, user, invitation_token)

    # Handle architect registration
    if user_role == UserRole.architect:
        # Prevent setting client-only fields
        user.firm_id = None
        user.is_firm_admin = False

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email
    verification = await create_email_verification(db, user)
    send_verification_email(user.email, verification.token)

    logger.info("User registered", extra={"user_id": user.id, "role": role})
    return user


async def _validate_and_consume_invitation(
    db: AsyncSession,
    user: User,
    token: str,
) -> None:
    """Validate an invitation token and grant project access to the new client."""
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation",
        )

    if invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has already been used",
        )

    if invitation.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired",
        )

    # Mark invitation as used
    invitation.is_used = True

    # Add user as project member
    member = ProjectMember(
        project_id=invitation.project_id,
        user_id=user.id,
        role="client",
    )
    db.add(member)


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> dict:
    """Authenticate a user and return access + refresh tokens."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        logger.warning("Login failed: user not found or inactive", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(password, user.hashed_password):
        logger.warning("Login failed: invalid password", extra={"user_id": user.id})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        firm_id=user.firm_id,
    )
    refresh_token = create_refresh_token(subject=user.id)

    logger.info("Login successful", extra={"user_id": user.id, "role": user.role.value})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def refresh_access_token(
    refresh_token: str,
) -> dict:
    """Validate a refresh token and issue a new access token."""
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )
    try:
        subject = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed subject",
        ) from None

    # Note: We don't look up the user here since we don't have a db session.
    # The access token will contain the user_id which is validated on next request.
    # For proper token rotation, you'd store refresh tokens in a database.
    access_token = create_access_token(
        subject=subject,
        role=payload.get("role", "architect"),
        firm_id=payload.get("firm_id"),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


async def create_email_verification(
    db: AsyncSession,
    user: User,
) -> EmailVerification:
    """Create an email verification token for a user."""
    token = create_url_safe_token()
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    return verification


async def verify_email(db: AsyncSession, token: str) -> User:
    """Verify a user's email using the verification token."""
    result = await db.execute(select(EmailVerification).where(EmailVerification.token == token))
    verification = result.scalar_one_or_none()

    if not verification or verification.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    if verification.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired",
        )

    verification.is_used = True

    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_verified = True
        await db.commit()
        await db.refresh(user)

    return user


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Initiate password reset by sending a reset token via email."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Always return 200 to prevent email enumeration
    if not user or not user.is_active:
        return

    token = create_url_safe_token()
    reset = PasswordReset(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(reset)
    await db.commit()

    send_password_reset_email(user.email, token)


async def reset_password(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    """Reset a user's password using a valid reset token."""
    result = await db.execute(select(PasswordReset).where(PasswordReset.token == token))
    reset = result.scalar_one_or_none()

    if not reset or reset.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if reset.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    reset.is_used = True

    result = await db.execute(select(User).where(User.id == reset.user_id))
    user = result.scalar_one_or_none()
    if user:
        user.hashed_password = hash_password(new_password)
        await db.commit()
