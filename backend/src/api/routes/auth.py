"""Auth routes: registration, login, token refresh, password reset, email verification."""

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import JSONResponse

from src.api.dependencies import DBSession, get_current_user
from src.core.config import settings
from src.core.rate_limit import RateLimiter
from src.models.user import User
from src.schemas.user import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from src.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

login_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_limiter = RateLimiter(max_requests=3, window_seconds=3600)
forgot_password_limiter = RateLimiter(max_requests=3, window_seconds=3600)
reset_password_limiter = RateLimiter(max_requests=5, window_seconds=3600)


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
    return {"id": user.id, "message": "Registration successful. Check your email to verify your account."}


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
