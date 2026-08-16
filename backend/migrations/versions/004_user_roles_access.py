"""Fine-grained user roles: admin sub-role + client secure-link access

- ``user_role`` enum gains ``admin`` (app superuser)
- ``projects`` gains ``client_token`` + ``client_password_hash`` for the
  secure-link client access flow (no sign-up required)

Revision ID: 004
Revises: 003
Create Date: 2026-08-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── App-level admin role (superuser) ────────────────────────────
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin'")

    # ── Client secure-link access per project ───────────────────────
    # client_token: unguessable link token (the "secure link").
    # client_password_hash: password the owner/admin sets; the client
    # enters it on the link page to get a scoped session (no sign-up).
    op.execute(
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_token VARCHAR(64) UNIQUE"
    )
    op.execute(
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_password_hash VARCHAR(255)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_client_token ON projects(client_token)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_projects_client_token")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS client_password_hash")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS client_token")
    # PostgreSQL cannot drop enum values; leave 'admin' in place.
