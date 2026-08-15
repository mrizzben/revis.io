# Data Model: Internal Team Collaboration

Feature: [spec.md](./spec.md) | Branch: `004-team-collaboration`

## Overview

Extends the existing revis.io schema. One existing table changes behavior (`project_members.role` gains a value); three new tables are added (`internal_notes`, `mentions`, `to_dos`); `notifications` gains enum values. Access to all internal content is gated on a per-project **collaborator** membership.

## Entities

### ProjectMember (existing — extended)

- **Represents**: A user's membership in a project.
- **Changes**: `role` string column (`default="client"`) additionally accepts `"collaborator"`.
- **Attributes**: `project_id` (PK/FK → projects), `user_id` (PK/FK → users), `role` (`client` | `collaborator`), `joined_at`.
- **Relationships**: belongs to `Project` and `User`.
- **Rules**: A user may hold one membership row per project. Owner is identified by `Project.owner_id` (not a ProjectMember row). `role == 'client'` members are external; `role == 'collaborator'` members + the owner form the internal team.

### InternalNote

- **Represents**: An internal-only note on a project, scoped to the internal team.
- **Attributes**:
  - `id` (PK, int)
  - `project_id` (FK → projects, ondelete CASCADE, not null)
  - `author_id` (FK → users, not null)
  - `parent_id` (FK → internal_notes, nullable) — if set, this row is a **reply** to the top-level note identified by `parent_id`.
  - `body` (Text, not null)
  - `created_at`, `updated_at` (DateTime)
- **Relationships**: `project`, `author`, `parent` (self-ref), `replies` (self-ref), `mentions` (→ Mention).
- **Rules**: `parent_id` always references a top-level note (no nested >1 level in v1 — replies are flat, matching `Comment`). Every row — reply or note — is visible only to the project's internal team. Optional association to a design file is deferred to v1 (not modeled) per spec assumption.

### Mention

- **Represents**: An `@mention` of a collaborator within a top-level internal note.
- **Attributes**:
  - `id` (PK, int)
  - `note_id` (FK → internal_notes, ondelete CASCADE, not null)
  - `user_id` (FK → users, not null)
  - `notified` (Bool, default false) — whether the mention notification has been emitted for this row.
  - `created_at` (DateTime)
- **Relationships**: `note`, `user` (mentioned user).
- **Rules**: `user_id` must be an internal-team member (collaborator or owner) of the note's project at mention time; mentioning a non-member either resolves against current members or prompts the owner to add them (spec edge case). Unique on `(note_id, user_id)`.

### ToDo

- **Represents**: An internal, assignable task within a project.
- **Attributes**:
  - `id` (PK, int)
  - `project_id` (FK → projects, ondelete CASCADE, not null)
  - `created_by` (FK → users, not null)
  - `assignee_id` (FK → users, nullable)
  - `title` (String(255), not null)
  - `description` (Text, nullable)
  - `status` (String, `open` | `complete`, default `open`)
  - `created_at`, `updated_at` (DateTime)
- **Relationships**: `project`, `created_by`, `assignee`.
- **Rules**: Only internal-team members may see or operate on a project's to-dos. Reassigning or completion creates/updates an in-app `Notification` (and email where resend configured) to the assignee. `assignee_id` must be an internal-team member when set.

### Notification (existing — extended)

- **Represents**: In-app (and email) notifications to a user.
- **Changes**: `NotificationType` enum (`backend/src/models/notification.py`) adds `mention` and `todo_assigned` values.
- **Attributes**: unchanged (`user_id`, `type`, `title`, `body`, `is_read`, `reference_id`, `created_at`).
- **Rules**: Mention notifications target the mentioned `user_id`; to-do assignment targets the `assignee_id`.

## Relationships Summary

```text
Project 1───* ProjectMember (role: client | collaborator)
Project 1───* InternalNote ──* Mention *──1 User   (mentioned)
InternalNote 1───* InternalNote (self-ref replies via parent_id)
Project 1───* ToDo *──1 User (assignee)

User 1───* ProjectMember
```

## Validation Rules (from spec FR + edge cases)

- Internal content must never be serialized into client-facing project/comment/file responses.
- Adding a collaborator requires the caller to be the project **owner**; removing a collaborator also requires owner, immediate revocation.
- Creating/reading/updating notes, replies, mentions, and to-dos requires the caller to be the internal team (owner or collaborator).
- Removed collaborators lose internal access immediately; their assigned to-dos must be surfaced to the owner/reassignable.
- Owner removal of a member with open to-dos: to-do remains, flagged to owner.

## State Transitions

**ToDo.status**: `open ⇄ complete` (edit/reassign any time; delete allowed by internal team with permission).

**ProjectMember.role** (add/remove): membership added by owner (`collaborator`), removed by owner (row deleted). A removed member is re-added as a fresh membership row.
