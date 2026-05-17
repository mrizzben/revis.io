"""Pydantic schemas for authentication and user management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.core.sanitize import sanitize_text


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., pattern="^(architect|client)$")
    invitation_token: Optional[str] = Field(None, description="Required for client registration")

    @field_validator("name", mode="after")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v) if isinstance(v, str) else v


class LoginRequest(BaseModel):
    """Request schema for login (form-encoded: username=email, password)."""

    username: str = Field(..., description="User email")
    password: str


class TokenResponse(BaseModel):
    """Response schema for successful authentication."""

    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request schema for token refresh (cookie-based, no body needed)."""

    pass


class ForgotPasswordRequest(BaseModel):
    """Request schema for password reset initiation."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset with token."""

    token: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """Response schema for user profile data."""

    id: int
    email: str
    name: str
    role: str
    firm_id: int | None
    is_firm_admin: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FirmResponse(BaseModel):
    """Response schema for firm data."""

    id: int
    name: str
    member_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateFirmRequest(BaseModel):
    """Request schema for creating a firm."""

    name: str = Field(..., min_length=1, max_length=255)


class AddFirmMemberRequest(BaseModel):
    """Request schema for adding a member to a firm."""

    email: EmailStr
