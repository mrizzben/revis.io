"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # S3 / RustFS
    S3_ENDPOINT: str | None = None
    S3_PRESIGNED_ENDPOINT: str | None = (
        None  # External endpoint for presigned URLs (browser-facing)
    )
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "revis.io"
    S3_REGION: str = "us-east-1"

    # Malware scanning (T8) — clamd over TCP; empty host disables scanning.
    CLAMD_HOST: str = ""
    CLAMD_PORT: int = 3310
    # Largest object scanned synchronously at upload-complete; larger objects
    # are marked `skipped` and must be scanned out-of-band before client issue.
    MALWARE_SCAN_MAX_SIZE: int = 524_288_000  # 500 MB
    # Abandoned multipart uploads older than this are aborted by maintenance.
    MULTIPART_ABANDON_AFTER_SECONDS: int = 7 * 24 * 3600
    # Soft-deleted design items are hard-deleted after this retention window.
    SOFT_DELETE_RETENTION_SECONDS: int = 30 * 24 * 3600

    # Email
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@revis.io.dev"

    # Google OAuth (sign in / sign up with Google). Empty client id disables OAuth.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()  # pyright: ignore[reportCallIssue]  # SECRET_KEY/DATABASE_URL come from .env via pydantic-settings
