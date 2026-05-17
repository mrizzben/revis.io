"""Initial schema - all 11 tables

Revision ID: 001
Revises:
Create Date: 2026-05-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE IF NOT EXISTS user_role AS ENUM ('architect', 'client')")
    op.execute("CREATE TYPE IF NOT EXISTS thumbnail_status AS ENUM ('pending', 'processing', 'complete', 'failed', 'unsupported')")
    op.execute("CREATE TYPE IF NOT EXISTS notification_type AS ENUM ('file_uploaded', 'milestone_completed', 'comment_replied', 'invitation_received')")

    # Create tables using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS firms (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role user_role NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            is_verified BOOLEAN DEFAULT false NOT NULL,
            firm_id INTEGER,
            is_firm_admin BOOLEAN DEFAULT false NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (firm_id) REFERENCES firms(id) ON DELETE SET NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_firm ON users(firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            owner_id INTEGER NOT NULL,
            firm_id INTEGER,
            is_archived BOOLEAN DEFAULT false NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (firm_id) REFERENCES firms(id) ON DELETE SET NULL,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_firm ON projects(firm_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role VARCHAR(20) DEFAULT 'client' NOT NULL,
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS invitations (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            token VARCHAR(64) NOT NULL,
            project_id INTEGER NOT NULL,
            invited_by_id INTEGER NOT NULL,
            is_used BOOLEAN DEFAULT false NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (invited_by_id) REFERENCES users(id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(email)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            position INTEGER DEFAULT 0 NOT NULL,
            is_completed BOOLEAN DEFAULT false NOT NULL,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id, position)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS design_files (
            id UUID PRIMARY KEY,
            project_id INTEGER NOT NULL,
            milestone_id INTEGER,
            uploaded_by_id INTEGER NOT NULL,
            filename VARCHAR(512) NOT NULL,
            file_type VARCHAR(20) NOT NULL,
            content_type VARCHAR(127) NOT NULL,
            file_size BIGINT NOT NULL,
            s3_key VARCHAR(1024) NOT NULL,
            thumbnail_small_key VARCHAR(1024),
            thumbnail_medium_key VARCHAR(1024),
            thumbnail_status thumbnail_status DEFAULT 'pending' NOT NULL,
            preview_glb_key VARCHAR(1024),
            preview_status VARCHAR(20),
            is_deleted BOOLEAN DEFAULT false NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (milestone_id) REFERENCES milestones(id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_id) REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_design_files_project ON design_files(project_id, is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_design_files_milestone ON design_files(milestone_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_design_files_thumbnail ON design_files(thumbnail_status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS file_versions (
            id SERIAL PRIMARY KEY,
            file_id UUID NOT NULL,
            version_number INTEGER NOT NULL,
            s3_key VARCHAR(1024) NOT NULL,
            file_size BIGINT NOT NULL,
            uploaded_by_id INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (file_id) REFERENCES design_files(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_id) REFERENCES users(id),
            UNIQUE (file_id, version_number)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_file_versions_file ON file_versions(file_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            file_id UUID NOT NULL,
            author_id INTEGER NOT NULL,
            parent_id INTEGER,
            body TEXT NOT NULL,
            is_resolved BOOLEAN DEFAULT false NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (author_id) REFERENCES users(id),
            FOREIGN KEY (file_id) REFERENCES design_files(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_file ON comments(file_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS email_verifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token VARCHAR(64) NOT NULL,
            is_used BOOLEAN DEFAULT false NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (token)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token VARCHAR(64) NOT NULL,
            is_used BOOLEAN DEFAULT false NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (token)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type notification_type NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            is_read BOOLEAN DEFAULT false NOT NULL,
            reference_id INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS password_resets")
    op.execute("DROP TABLE IF EXISTS email_verifications")
    op.execute("DROP TABLE IF EXISTS comments")
    op.execute("DROP TABLE IF EXISTS file_versions")
    op.execute("DROP TABLE IF EXISTS design_files")
    op.execute("DROP TABLE IF EXISTS milestones")
    op.execute("DROP TABLE IF EXISTS invitations")
    op.execute("DROP TABLE IF EXISTS project_members")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS firms")
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS thumbnail_status")
    op.execute("DROP TYPE IF EXISTS user_role")
