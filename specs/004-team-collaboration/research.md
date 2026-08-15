# Research: Internal Team Collaboration

Feature: [spec.md](./spec.md) | Branch: `004-team-collaboration`

## Decisions

The feature's technical unknowns were resolved by inspecting the existing revis.io codebase rather than by open-ended research — all choices follow established project conventions.

### Decision: Reuse `project_members.role` for internal membership (no new member table)

- **Decision**: Add a `collaborator` value to the existing `ProjectMember.role` string column; keep `client` for client members.
- **Rationale**: `ProjectMember` (`backend/src/models/project.py`) already models per-project user membership with a free-form `role` column defaulting to `"client"`. Reusing it avoids a parallel table and keeps collaborator access scoped per-project exactly like client access. The existing `Project.members` relationship enumerates all members, so filtering `role != 'client'` yields collaborators.
- **Alternatives considered**: A dedicated `project_collaborators` table — rejected as redundant; the role discriminator is already present and used for access checks.

### Decision: Internal notes as top-level thread with reply rows (self-referencing parent)

- **Decision**: New `internal_notes` table (a note row) with replies stored as `internal_notes` rows carrying a `parent_id` referencing the top-level note — mirroring the existing `Comment.parent_id` self-reference in `backend/src/models/comment.py`.
- **Rationale**: Matches the proven comment-threading pattern already in the codebase, minimizing new concepts and enabling the same eager-loading/reply logic.
- **Alternatives considered**: A separate `internal_note_replies` table — rejected for unnecessary symmetry against the existing `Comment` pattern.

### Decision: `mentions` join table resolving @name → user + note + notification

- **Decision**: A `mentions` table keyed `(note_id, user_id)` storing each mentioned collaborator, with a `notified` flag. Mention resolution fan-out creates an in-app `Notification` (and email for the existing resend path where configured).
- **Rationale**: An explicit join row makes mention resolution idempotent and queryable, and cleanly separates "who was mentioned" from the note body text. Reuses `Notification` (`backend/src/models/notification.py`).
- **Alternatives considered**: Parsing `@handle` from note text at render time — rejected as fragile (renames, dangling names, no persisted notification record).

### Decision: To-dos as a self-contained table

- **Decision**: New `to_dos` table keyed to `project_id` with `title`, `description`, `assignee_id`, `status` (open/complete), `created_by`. Assignment/assignment-changes and status transitions create a `Notification` for the assignee.
- **Rationale**: Simple, matches the spec's minimal on-project task model (no subtasks, no due dates in v1).
- **Alternatives considered**: A generic tasks engine (due dates, priorities, tags) — rejected as YAGNI; explicitly out of v1 scope per spec assumptions.

### Decision: Shared internal-access gate via new FastAPI dependencies

- **Decision**: Add `require_project_collaborator(...)` (owner or collaborator) and `require_project_owner(...)` dependency factories in `backend/src/api/dependencies.py`, mirroring existing `require_role(...)`, and a `project_service`-style access check.
- **Rationale**: Centralizes the "internal only" rule so every internal endpoint and the client-facing serializers share one guard — the single point where the client-hiding guarantee is enforced. Reuses the existing `get_current_user` / token dependency chain.
- **Alternatives considered**: Inline per-route checks — rejected; duplicated checks are error-prone for a security-sensitive boundary.

### Decision: Real-time via existing WebSocket broadcast, not a new event bus

- **Decision**: Extend `backend/src/websocket/handlers.py` to broadcast internal-note and to-do events to the project's connected team (owner + collaborators), excluding clients.
- **Rationale**: The existing WebSocket channel already propagates model changes to project viewers; reusing it keeps the "connected team sees updates in <10s" criterion without new infrastructure.
- **Alternatives considered**: A separate internal-only WebSocket topic and SSE stream — rejected as overkill at the stated scale; polling fallback (per spec assumption) covers disconnected users.

## External references

- No new third-party libraries. Open-source reinforcements: SQLAlchemy self-referential relationships and FastAPI dependency hardening follow the project's existing usage; no new integration pattern was introduced.
