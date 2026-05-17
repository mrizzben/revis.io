"""JWT token creation/validation and password hashing with pwdlib (Argon2)."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from src.core.config import settings

password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    subject: int,
    role: str,
    firm_id: int | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Token payload: {sub: user_id, role, firm_id, type: "access", exp, iat}
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    if firm_id is not None:
        payload["firm_id"] = firm_id

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(
    subject: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token.

    Token payload: {sub: user_id, type: "refresh", exp, iat}
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


def create_url_safe_token(length: int = 32) -> str:
    """Create a URL-safe random token for invitations, email verification, etc."""
    import secrets
    return secrets.token_urlsafe(length)
