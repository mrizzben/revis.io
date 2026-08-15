"""Revision management: versions, checkpoints, reviews, activity, options

Revision ID: 003
Revises: 002
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Revision lifecycle on file_versions ─────────────────────────
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS revision_message VARCHAR(512)")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS name VARCHAR(255)")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS content_hash VARCHAR(128)")
    op.execute(
        "ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'internal'"
    )
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS issued_by_id INTEGER")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS issued_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS superseded_by_id INTEGER")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS milestone_id INTEGER")
    op.execute(
        "ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS scan_status VARCHAR(20) NOT NULL DEFAULT 'pending'"
    )
    op.execute("ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS mime_valid BOOLEAN NOT NULL DEFAULT true")
    op.execute(
        "ALTER TABLE file_versions ADD COLUMN IF NOT EXISTS restored_from_superseded BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_versions_visibility ON file_versions(file_id, visibility)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_versions_hash ON file_versions(content_hash)"
    )

    # ── Design options (T5) ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS design_options (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            is_current BOOLEAN NOT NULL DEFAULT false,
            is_archived BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_design_options_project ON design_options(project_id)")

    op.execute(
        "ALTER TABLE design_files ADD COLUMN IF NOT EXISTS design_option_id INTEGER"
    )
    op.execute(
        "ALTER TABLE design_files ADD COLUMN IF NOT EXISTS parent_file_id UUID"
    )
    op.execute(
        "ALTER TABLE design_files ADD COLUMN IF NOT EXISTS current_version_id INTEGER"
    )

    # ── Activity / audit history (T6) ───────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS activity_events (
            id BIGSERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            entity_type VARCHAR(64) NOT NULL,
            entity_id VARCHAR(64),
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            visibility VARCHAR(20) NOT NULL DEFAULT 'internal',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_id) REFERENCES users(id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_project_time ON activity_events(project_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_events(event_type)"
    )

    # ── Reviews (T3) ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            file_id UUID NOT NULL,
            revision_id INTEGER,
            requested_by_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'draft',
            is_client_review BOOLEAN NOT NULL DEFAULT false,
            decision_comment TEXT,
            decided_by_id INTEGER,
            decided_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (file_id) REFERENCES design_files(id) ON DELETE CASCADE,
            FOREIGN KEY (revision_id) REFERENCES file_versions(id) ON DELETE SET NULL,
            FOREIGN KEY (requested_by_id) REFERENCES users(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id),
            FOREIGN KEY (decided_by_id) REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_file ON reviews(file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_project ON reviews(project_id)")

    # ── Comments: revision scoping + resolution audit (T1/T3) ───────
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS version_id INTEGER")
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE comments ADD COLUMN IF NOT EXISTS resolved_by_id INTEGER")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_comments_version ON comments(version_id)"
    )

    # ── Notification types (T3/T2) ──────────────────────────────────
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'review_requested'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'review_updated'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'revision_issued'")

    # ── FK constraints (added after columns exist; circular fk handled) ──
    op.execute(
        "ALTER TABLE design_files ADD CONSTRAINT fk_design_files_option FOREIGN KEY (design_option_id) REFERENCES design_options(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE design_files ADD CONSTRAINT fk_design_files_current_version FOREIGN KEY (current_version_id) REFERENCES file_versions(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_issued_by FOREIGN KEY (issued_by_id) REFERENCES users(id)"
    )
    op.execute(
        "ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_superseded_by FOREIGN KEY (superseded_by_id) REFERENCES users(id)"
    )
    op.execute(
        "ALTER TABLE file_versions ADD CONSTRAINT fk_file_versions_milestone FOREIGN KEY (milestone_id) REFERENCES milestones(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE comments ADD CONSTRAINT fk_comments_version FOREIGN KEY (version_id) REFERENCES file_versions(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE comments ADD CONSTRAINT fk_comments_resolved_by FOREIGN KEY (resolved_by_id) REFERENCES users(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE comments DROP CONSTRAINT IF EXISTS fk_comments_resolved_by")
    op.execute("ALTER TABLE comments DROP CONSTRAINT IF EXISTS fk_comments_version")
    op.execute("ALTER TABLE file_versions DROP CONSTRAINT IF EXISTS fk_file_versions_milestone")
    op.execute("ALTER TABLE file_versions DROP CONSTRAINT IF EXISTS fk_file_versions_superseded_by")
    op.execute("ALTER TABLE file_versions DROP CONSTRAINT IF EXISTS fk_file_versions_issued_by")
    op.execute("ALTER TABLE design_files DROP CONSTRAINT IF EXISTS fk_design_files_current_version")
    op.execute("ALTER TABLE design_files DROP CONSTRAINT IF EXISTS fk_design_files_option")
    op.execute("DROP TABLE IF EXISTS reviews")
    op.execute("DROP TABLE IF EXISTS activity_events")
    op.execute("ALTER TABLE design_files DROP COLUMN IF EXISTS current_version_id")
    op.execute("ALTER TABLE design_files DROP COLUMN IF EXISTS parent_file_id")
    op.execute("ALTER TABLE design_files DROP COLUMN IF EXISTS design_option_id")
    op.execute("DROP TABLE IF EXISTS design_options")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS resolved_by_id")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS resolved_at")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS version_id")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS restored_from_superseded")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS mime_valid")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS scan_status")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS milestone_id")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS superseded_at")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS superseded_by_id")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS issued_at")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS issued_by_id")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS visibility")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS content_hash")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS description")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS name")
    op.execute("ALTER TABLE file_versions DROP COLUMN IF EXISTS revision_message")
    # Enum values cannot be removed in Postgres; left in place (harmless) on downgrade.
