"""Auth routes: registration, login, token refresh, password reset, email verification, Google OAuth."""

import logging
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.api.dependencies import DBSession
from src.core.config import settings
from src.core.rate_limit import RateLimiter
from src.schemas.user import (
    ForgotPasswordRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from src.services import auth as auth_service
from src.services import oauth as oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

login_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_limiter = RateLimiter(max_requests=3, window_seconds=3600)
forgot_password_limiter = RateLimiter(max_requests=3, window_seconds=3600)
reset_password_limiter = RateLimiter(max_requests=5, window_seconds=3600)
oauth_callback_limiter = RateLimiter(max_requests=10, window_seconds=3600)


@router.get("/providers")
async def auth_providers():
    """Public: which social auth providers are available."""
    return {"google": oauth_service.oauth_enabled()}


@router.get("/google/authorize")
async def google_authorize():
    """Start Google OAuth: set a state cookie and redirect to Google's consent screen."""
    if not oauth_service.oauth_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    state = secrets.token_urlsafe(32)
    response = RedirectResponse(oauth_service.build_google_auth_url(state), status_code=302)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,  # 10 minutes: enough for the consent round-trip
        path="/api/auth/google",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: DBSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    _rate: None = Depends(oauth_callback_limiter),
):
    """Handle Google's redirect: verify state, exchange the code, log in or sign up."""
    if error:
        logger.warning("Google OAuth error", extra={"error": error})
        return _oauth_error_redirect("google_oauth_failed")

    expected_state = request.cookies.get("oauth_state")
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        logger.warning("Google OAuth state mismatch")
        return _oauth_error_redirect("invalid_state")

    if not code:
        return _oauth_error_redirect("google_oauth_failed")

    try:
        tokens = await oauth_service.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        if not access_token:
            return _oauth_error_redirect("google_oauth_failed")
        profile = await oauth_service.fetch_google_userinfo(access_token)
        user, _created = await oauth_service.login_or_create_google_user(db, profile)
        tokens = await oauth_service.issue_tokens(user)
    except HTTPException:
        return _oauth_error_redirect("google_oauth_failed")

    response = RedirectResponse(
        f"{settings.FRONTEND_URL}/oauth/callback#access_token={tokens['access_token']}&token_type=bearer",
        status_code=302,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )
    return response


def _oauth_error_redirect(error_code: str) -> RedirectResponse:
    """Redirect back to the SPA login page with an error code."""
    return RedirectResponse(f"{settings.FRONTEND_URL}/login?error={error_code}", status_code=302)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: DBSession,
    _rate: None = Depends(register_limiter),
):
    """Register a new user (architect or client with invitation token)."""
    user = await auth_service.register_user(
        db=db,
        email=request.email,
        password=request.password,
        name=request.name,
        role=request.role,
        invitation_token=request.invitation_token,
    )
    return {
        "id": user.id,
        "message": "Registration successful. Check your email to verify your account.",
    }


@router.post("/login")
async def login(
    response: Response,
    db: DBSession,
    username: str = Form(..., description="User email"),
    password: str = Form(...),
    _rate: None = Depends(login_limiter),
):
    """Login with email and password (form-encoded)."""
    tokens = await auth_service.login_user(
        db=db,
        email=username,
        password=password,
    )

    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )

    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
):
    """Refresh the access token using the refresh_token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "No refresh token"},
        )

    tokens = await auth_service.refresh_access_token(refresh_token)
    return tokens


@router.post("/logout")
async def logout(response: Response):
    """Logout by clearing the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
    )
    return {"message": "Logged out"}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DBSession,
    _rate: None = Depends(forgot_password_limiter),
):
    """Request a password reset email."""
    await auth_service.forgot_password(db=db, email=request.email)
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: DBSession,
    _rate: None = Depends(reset_password_limiter),
):
    """Reset password using a valid reset token."""
    await auth_service.reset_password(
        db=db,
        token=request.token,
        new_password=request.new_password,
    )
    return {"message": "Password reset successfully"}


@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
    db: DBSession,
):
    """Verify email address using verification token."""
    await auth_service.verify_email(db=db, token=token)
    return {"message": "Email verified successfully"}
