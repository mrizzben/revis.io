"""Google OAuth: build the authorization URL, exchange the code, find-or-create the user.

The whole flow is a browser redirect chain (frontend -> /auth/google/authorize ->
accounts.google.com -> /auth/google/callback -> frontend), so no CORS is involved.
httpx does the two server-side Google API calls (token exchange + userinfo).
"""

import logging
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import create_access_token, create_refresh_token
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
OAUTH_SCOPES = "openid email profile"


def oauth_enabled() -> bool:
    """OAuth is enabled when a Google client id is configured."""
    return bool(settings.GOOGLE_CLIENT_ID)


def build_google_auth_url(state: str) -> str:
    """Build the Google consent URL the browser is redirected to."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange the authorization code for an access token at Google."""
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
    except httpx.HTTPError as exc:
        logger.warning("Google token exchange failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach Google OAuth",
        ) from exc
    if resp.status_code != 200:
        logger.warning(
            "Google token exchange rejected", extra={"status": resp.status_code, "body": resp.text[:200]}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google rejected the authorization code",
        )
    return resp.json()


async def fetch_google_userinfo(access_token: str) -> dict:
    """Fetch the verified Google profile (email, name, picture) for the token."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Google userinfo failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach Google OAuth",
        ) from exc
    if resp.status_code != 200:
        logger.warning(
            "Google userinfo rejected", extra={"status": resp.status_code, "body": resp.text[:200]}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to fetch Google profile",
        )
    return resp.json()


async def login_or_create_google_user(db: AsyncSession, profile: dict) -> tuple[User, bool]:
    """Find the user by Google's verified email, creating one if missing.

    Google verifies email ownership, so an existing email/password account is
    safely linked: the Google user is logged into it (and the email is marked
    verified). New users are created as architects with no password.
    """
    email = (profile.get("email") or "").lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        if not user.is_verified:
            user.is_verified = True
        if not user.name and profile.get("name"):
            user.name = profile["name"].strip()[:255]
        await db.commit()
        await db.refresh(user)
        return user, False

    user = User(
        email=email,
        name=(profile.get("name") or email.split("@")[0]).strip()[:255],
        hashed_password=None,  # OAuth-only account; no password to log in with
        role=UserRole.architect,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("User registered via Google OAuth", extra={"user_id": user.id, "email": email})
    return user, True


async def issue_tokens(user: User) -> dict:
    """Issue access + refresh tokens for a user (same shape as password login)."""
    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        firm_id=user.firm_id,
    )
    refresh_token = create_refresh_token(subject=user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
