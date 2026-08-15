"""Internal collaboration: notes, mentions, to-dos

Revision ID: 002
Revises: 001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New notification types for @mentions and to-do assignments (PG12+ allows in-transaction)
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'mention'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'todo_assigned'")

    # Internal notes (top-level parent_id NULL) + replies (parent_id set)
    op.execute("""
        CREATE TABLE IF NOT EXISTS internal_notes (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            parent_id INTEGER,
            body TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES users(id),
            FOREIGN KEY (parent_id) REFERENCES internal_notes(id) ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_internal_notes_project ON internal_notes(project_id, created_at)"
    )

    # @Mentions — a mentioned user within a top-level internal note
    op.execute("""
        CREATE TABLE IF NOT EXISTS mentions (
            id SERIAL PRIMARY KEY,
            note_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            notified BOOLEAN DEFAULT false NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (note_id) REFERENCES internal_notes(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (note_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_mentions_user ON mentions(user_id)")

    # To-dos — internal assignable tasks
    op.execute("""
        CREATE TABLE IF NOT EXISTS to_dos (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            assignee_id INTEGER,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'open' NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assignee_id) REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_to_dos_project ON to_dos(project_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS to_dos")
    op.execute("DROP TABLE IF EXISTS mentions")
    op.execute("DROP TABLE IF EXISTS internal_notes")
    # Enum values cannot be REMOVED in Postgres; left in place (harmless) on downgrade.
