# Contracts: Internal Team Collaboration

REST API contracts for internal team collaboration. All endpoints are under `/api`, require a valid access token (`Authorization: Bearer <jwt>`), and follow existing auth/error conventions (`401` unauthenticated, `403` forbidden, `404` not found).

Auth rule summary:

- **Owner** = `Project.owner_id == current_user.id` → full internal control (add/remove collaborators, CRUD notes/to-dos).
- **Collaborator** = a `ProjectMember` row with `role == 'collaborator'` → read/write internal content (notes, replies, to-dos); cannot add/remove collaborators.
- **Client** = a `ProjectMember` row with `role == 'client'`, or a user with no membership → **never** sees internal content (these endpoints return `404`).

## Collaborators

### `GET /api/projects/{project_id}/collaborators`

Lists the project's internal team (owner + collaborators).

- **Auth**: owner or collaborator.
- **Response 200**: `{ "collaborators": [ { "user_id", "email", "name", "role", "joined_at" } ], "owner": { "user_id", "email", "name" } }`

### `POST /api/projects/{project_id}/collaborators`

Add a collaborator by email or user id.

- **Auth**: owner only.
- **Request** (Pydantic): `{ "email": string, "role": "collaborator" }` (or `{ "user_id": int }`).
- **Validation**: Target user exists and is active; is not the owner; if already a member, role is updated to `collaborator` (idempotent).
- **Response 201**: `{ "user_id", "email", "name", "role", "joined_at" }`

### `DELETE /api/projects/{project_id}/collaborators/{user_id}`

Remove a collaborator (immediate access revocation).

- **Auth**: owner only.
- **Response 204**: no content.
- **Side effects**: Mention/notification fan-out is not retroactively removed; the member's open to-dos remain and are surfaced to the owner.

## Internal Notes

### `GET /api/projects/{project_id}/internal-notes`

Lists top-level internal notes (with replies nested) for the project.

- **Auth**: owner or collaborator.
- **Response 200**: `{ "notes": [ { "id", "author": { "id", "name" }, "body", "mentions": [ {"user_id","name"} ], "replies": [ { "id", "author": { "id","name" }, "body", "created_at" } ], "created_at", "updated_at" } ] }`

### `POST /api/projects/{project_id}/internal-notes`

Create a top-level internal note.

- **Auth**: owner or collaborator.
- **Request** (Pydantic): `{ "body": string, "mentions": [ int ...user_ids ] }` (mentions optional).
- **Validation**: `body` non-empty (sanitized via existing `sanitize`); each `mentions` id must be an internal-team member.
- **Response 201**: created note DTO (as above).
- **Side effects**: Creates `Mention` rows; for each, emits `Notification` (type `mention`) and broadcasts a `internal_note.created` WebSocket event to the project's connected team.

### `POST /api/projects/{project_id}/internal-notes/{note_id}/replies`

Create a reply to a top-level note.

- **Auth**: owner or collaborator.
- **Request** (Pydantic): `{ "body": string }`.
- **Validation**: `note_id` is a top-level note in this project.
- **Response 201**: reply DTO (`{ "id", "author", "body", "parent_id", "created_at" }`).

## To-Dos

### `GET /api/projects/{project_id}/todos`

Lists the project's to-dos.

- **Auth**: owner or collaborator.
- **Response 200**: `{ "todos": [ { "id", "title", "description", "status", "assignee": { "id","name" } | null, "created_by": { "id","name" }, "created_at", "updated_at" } ] }`

### `POST /api/projects/{project_id}/todos`

Create a to-do.

- **Auth**: owner or collaborator.
- **Request** (Pydantic): `{ "title": string, "description": string?, "assignee_id": int? }`.
- **Validation**: `title` non-empty; `assignee_id` must be an internal-team member when set.
- **Response 201**: to-do DTO.
- **Side effects**: If `assignee_id` set, emits `Notification` (type `todo_assigned`) to the assignee.

### `PATCH /api/projects/{project_id}/todos/{todo_id}`

Update a to-do (rename, description, status, reassign).

- **Auth**: owner or collaborator.
- **Request** (Pydantic, partial): any of `{ "title"?, "description"?, "status": "open"|"complete"?, "assignee_id"?: int|null }`.
- **Validation**: as per create.
- **Response 200**: updated to-do DTO.
- **Side effects**: Reassignment or completion emits `Notification` (type `todo_assigned`) to the new/current assignee.

### `DELETE /api/projects/{project_id}/todos/{todo_id}`

Delete a to-do.

- **Auth**: owner or collaborator.
- **Response 204**: no content.

## Error Conventions

- `401` — missing/invalid token.
- `403` — authenticated but insufficient role (e.g., client or non-owner attempting to add collaborators).
- `404` — project not found, or user is not internal team (client/non-member) — internal endpoints return `404` for external users to avoid existence disclosure.
