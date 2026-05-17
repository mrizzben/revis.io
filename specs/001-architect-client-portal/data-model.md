# Data Model: Architect-Client Design Portal

**Date**: 2026-05-09 | **Feature**: [spec.md](./spec.md)

## Entity-Relationship Diagram

```
Firm 1 ──── * User (role=architect)
                    │
                    │ owns (solo) / creates (firm)
                    ▼
                Project 1 ──── * Milestone
                    │                │
                    │ invites        │ groups
                    ▼                ▼
            Invitation          DesignFile 1 ──── * FileVersion
                    │                │
                    │ accepts        │ has
                    ▼                ▼
                User (role=client) Comment

User * ──── * Project    (via project_members)
```

## Tables

### users

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | Unique user identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Login email |
| `name` | VARCHAR(255) | NOT NULL | Display name |
| `hashed_password` | VARCHAR(255) | NOT NULL | Argon2-hashed password |
| `role` | ENUM('architect','client') | NOT NULL | User role |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Soft delete / deactivation |
| `is_verified` | BOOLEAN | NOT NULL, DEFAULT FALSE | Email verified |
| `firm_id` | INTEGER | FK → firms.id, NULLABLE | Firm membership (NULL = solo) |
| `is_firm_admin` | BOOLEAN | NOT NULL, DEFAULT FALSE | Firm admin flag |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation rules**:
- `email`: valid email format, max 255 chars
- `name`: 1-255 chars, trimmed
- `password`: min 8 chars (enforced in Pydantic schema, not DB)
- `role` change from 'architect' to 'client' (or vice versa) is forbidden after registration
- `firm_id` must be NULL when `role = 'client'`
- `is_firm_admin` must be FALSE when `role = 'client'` or `firm_id IS NULL`

**Indexes**: `(email)` UNIQUE, `(firm_id)`, `(role)`

### firms

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `name` | VARCHAR(255) | NOT NULL | Firm display name |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation**: `name` 1-255 chars, trimmed, unique per firm (not globally)

**Relationships**:
- `members`: list of Users with `firm_id = this.id`
- `projects`: list of Projects with `firm_id = this.id`

### projects

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `name` | VARCHAR(255) | NOT NULL | Project name |
| `description` | TEXT | NULLABLE | Optional description |
| `owner_id` | INTEGER | FK → users.id, NOT NULL | Creating architect |
| `firm_id` | INTEGER | FK → firms.id, NULLABLE | Owning firm (NULL = solo project) |
| `is_archived` | BOOLEAN | NOT NULL, DEFAULT FALSE | Soft archive |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation rules**:
- `owner_id` must reference a user with `role = 'architect'`
- If `firm_id` is set, `owner_id` must belong to that firm
- Archiving a project hides it from client dashboards but preserves data
- Project deletion cascades to: milestones, design_files, comments, invitations, project_members

**Indexes**: `(owner_id)`, `(firm_id)`

### project_members

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `project_id` | INTEGER | FK → projects.id, NOT NULL | |
| `user_id` | INTEGER | FK → users.id, NOT NULL | |
| `role` | VARCHAR(20) | NOT NULL, DEFAULT 'client' | 'client' |
| `joined_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Constraints**: UNIQUE(`project_id`, `user_id`), PK on composite

**Relationships**: Many-to-many between users (clients) and projects

### invitations

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `email` | VARCHAR(255) | NOT NULL, INDEX | Invitee email |
| `token` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | URL-safe random token |
| `project_id` | INTEGER | FK → projects.id, NOT NULL, CASCADE | |
| `invited_by_id` | INTEGER | FK → users.id, NOT NULL | Architect who sent invite |
| `is_used` | BOOLEAN | NOT NULL, DEFAULT FALSE | Consumed on registration |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiration timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation rules**:
- `token`: `secrets.token_urlsafe(32)` → ~43 chars
- Default expiry: 7 days from creation
- One active invitation per `(email, project_id)` — resending replaces the previous one

**State transitions**: `pending` (is_used=false, not expired) → `used` (is_used=true) or `expired` (expires_at < now)

### milestones

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `project_id` | INTEGER | FK → projects.id, NOT NULL, CASCADE | |
| `name` | VARCHAR(255) | NOT NULL | e.g., "Concept Design" |
| `description` | TEXT | NULLABLE | |
| `position` | INTEGER | NOT NULL, DEFAULT 0 | Order in timeline |
| `is_completed` | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| `completed_at` | TIMESTAMPTZ | NULLABLE | When marked complete |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation**: Milestones within a project must have unique `position` values (enforced at app level)

**Indexes**: `(project_id, position)`

### design_files

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | |
| `project_id` | INTEGER | FK → projects.id, NOT NULL, CASCADE | |
| `milestone_id` | INTEGER | FK → milestones.id, NULLABLE | Optional grouping |
| `uploaded_by_id` | INTEGER | FK → users.id, NOT NULL | |
| `filename` | VARCHAR(512) | NOT NULL | Original filename |
| `file_type` | VARCHAR(20) | NOT NULL | Extension: png, pdf, dwg, etc. |
| `content_type` | VARCHAR(127) | NOT NULL | MIME type |
| `file_size` | BIGINT | NOT NULL | Bytes |
| `s3_key` | VARCHAR(1024) | NOT NULL | S3 object key |
| `thumbnail_small_key` | VARCHAR(1024) | NULLABLE | |
| `thumbnail_medium_key` | VARCHAR(1024) | NULLABLE | |
| `thumbnail_status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | pending/processing/complete/failed/unsupported |
| `preview_glb_key` | VARCHAR(1024) | NULLABLE | 3D preview (IFC/OBJ/STL converted to glTF) |
| `preview_status` | VARCHAR(20) | NULLABLE | |
| `is_deleted` | BOOLEAN | NOT NULL, DEFAULT FALSE | Soft delete |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**State transitions for `thumbnail_status`**:
```
pending → processing → complete
                     → failed (retry up to 3 times)
                     → unsupported (SKP, RVT)
```

**Validation rules**:
- `file_type`: one of png, jpg, jpeg, webp, pdf, dwg, dxf, skp, rvt, ifc, obj, stl
- `file_size`: max 1,073,741,824 (1 GiB)
- `s3_key`: format `uploads/{project_id}/{uuid}/{filename}`

**Indexes**: `(project_id)`, `(milestone_id)`, `(project_id, is_deleted)`, `(thumbnail_status)`

### file_versions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `file_id` | UUID | FK → design_files.id, NOT NULL, CASCADE | |
| `version_number` | INTEGER | NOT NULL | Sequential 1, 2, 3... |
| `s3_key` | VARCHAR(1024) | NOT NULL | Previous version S3 key |
| `file_size` | BIGINT | NOT NULL | |
| `uploaded_by_id` | INTEGER | FK → users.id, NOT NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Constraints**: UNIQUE(`file_id`, `version_number`)

### comments

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `file_id` | UUID | FK → design_files.id, NOT NULL, CASCADE | |
| `author_id` | INTEGER | FK → users.id, NOT NULL | Client or architect |
| `parent_id` | INTEGER | FK → comments.id, NULLABLE | For threaded replies |
| `body` | TEXT | NOT NULL | Comment content |
| `is_resolved` | BOOLEAN | NOT NULL, DEFAULT FALSE | Architect marks resolved |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Validation rules**:
- `body`: 1-5000 characters, trimmed
- `author_id`: must have access to the parent file's project
- `parent_id`: if set, must reference a comment on the same file

**Indexes**: `(file_id, created_at)`, `(author_id)`

### email_verifications

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `user_id` | INTEGER | FK → users.id, NOT NULL, CASCADE | |
| `token` | VARCHAR(64) | UNIQUE, NOT NULL | |
| `is_used` | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| `expires_at` | TIMESTAMPTZ | NOT NULL | 24h from creation |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

### password_resets

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PK, AUTOINCREMENT | |
| `user_id` | INTEGER | FK → users.id, NOT NULL, CASCADE | |
| `token` | VARCHAR(64) | UNIQUE, NOT NULL | |
| `is_used` | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| `expires_at` | TIMESTAMPTZ | NOT NULL | 1h from creation |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

## SQL (PostgreSQL)

```sql
CREATE TYPE user_role AS ENUM ('architect', 'client');
CREATE TYPE thumbnail_status AS ENUM ('pending', 'processing', 'complete', 'failed', 'unsupported');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    firm_id INTEGER REFERENCES firms(id),
    is_firm_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE firms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    firm_id INTEGER REFERENCES firms(id),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'client',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE invitations (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    token VARCHAR(64) UNIQUE NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    invited_by_id INTEGER NOT NULL REFERENCES users(id),
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE milestones (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE design_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    milestone_id INTEGER REFERENCES milestones(id) ON DELETE SET NULL,
    uploaded_by_id INTEGER NOT NULL REFERENCES users(id),
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    content_type VARCHAR(127) NOT NULL,
    file_size BIGINT NOT NULL,
    s3_key VARCHAR(1024) NOT NULL,
    thumbnail_small_key VARCHAR(1024),
    thumbnail_medium_key VARCHAR(1024),
    thumbnail_status thumbnail_status NOT NULL DEFAULT 'pending',
    preview_glb_key VARCHAR(1024),
    preview_status VARCHAR(20),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE file_versions (
    id SERIAL PRIMARY KEY,
    file_id UUID NOT NULL REFERENCES design_files(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    s3_key VARCHAR(1024) NOT NULL,
    file_size BIGINT NOT NULL,
    uploaded_by_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (file_id, version_number)
);

CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    file_id UUID NOT NULL REFERENCES design_files(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id),
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE email_verifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE password_resets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_firm ON users(firm_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_firm ON projects(firm_id);
CREATE INDEX idx_invitations_email ON invitations(email);
CREATE INDEX idx_invitations_token ON invitations(token);
CREATE INDEX idx_milestones_project ON milestones(project_id, position);
CREATE INDEX idx_design_files_project ON design_files(project_id, is_deleted);
CREATE INDEX idx_design_files_milestone ON design_files(milestone_id);
CREATE INDEX idx_design_files_thumbnail ON design_files(thumbnail_status);
CREATE INDEX idx_comments_file ON comments(file_id, created_at);
CREATE INDEX idx_comments_author ON comments(author_id);
CREATE INDEX idx_file_versions_file ON file_versions(file_id);
```
