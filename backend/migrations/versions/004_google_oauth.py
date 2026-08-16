"""Google OAuth: users may have no password (OAuth-only accounts).

Revision ID: 004
Revises: 003
Create Date: 2026-08-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Google OAuth accounts sign in via Google, so they have no hashed password.
    op.execute("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")


def downgrade() -> None:
    # Invert only for fresh databases; pre-existing NULL rows must be fixed first.
    op.execute("ALTER TABLE users ALTER COLUMN hashed_password SET NOT NULL")
