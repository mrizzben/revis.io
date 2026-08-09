# Research: Scope Gap Analysis — Architect-Client Design Portal

**Date**: 2026
**Context**: App targets architects collaborating *internally* **and** with *clients*, updating progress in real time. This doc reviews the two existing feature specs and recommends what to add next.

---

## Current Scope (what's already specced)

### `specs/001-architect-client-portal`

- Project creation, file upload (1 GB, image/PDF/CAD/3D formats), previews/thumbnails
- Real-time updates to clients on upload/change
- Email notifications (when client not viewing)
- Milestones / phases with completion status + timeline
- Client feedback / comments on design files
- Invitations (unique secure links, resend/expiry) + access control
- Firm / role ownership (firm-owned projects, reassignment)
- Unified dashboard for each user

### `specs/003-kanban-board-view`

- Milestones rendered as columns, files as cards
- Drag-and-drop reassignment (architect only)
- Timeline ↔ board toggle
- Read-only board for clients

---

## The Core Gap

The app's stated goal is *"architects collaborate internally and to their clients."*
The specs fully cover the **architect → client** direction, but **internal team
collaboration is nearly absent** — only firm ownership + reassignment (an 001
edge case) exists. This is the biggest mismatch with the product's own positioning.

---

## Candidate Additions (roughly by priority)

| # | Candidate | Why it fits | Value |
| --- | ----------- | ------------- | ------- |
| 1 | **Internal team collaboration** — add collaborators to a project, internal-only notes/@mentions hidden from clients, assignable to-dos | Closes the "collaborate internally" half of the goal; biggest gap | Highest — **in progress** (see below) |
| 2 | **File versioning + change log** — upload new revisions, keep history, show visible "changed" state to clients | Already assumed by 3 edge cases in 001/003 ("preserve comments across versions", "update appears without re-navigate") but never specced | High |
| 3 | **Client approvals / sign-offs** — mark deliverable as approved / revisions requested | Tangible go/no-go signal; natural extension of milestones + feedback | High |
| 4 | **Activity feed / project timeline** — chronological record of uploads, milestone changes, comments | Gives the "progress tracking" half of the goal a home; cheap on top of existing events | Medium |
| 5 | **In-app notifications** — notification center/bell (currently email-only) | Explicit edge case in 001, currently unimplemented | Medium |

### Deferred (scope-creep risk)

- Side-by-side version comparison
- Public read-only share links
- Granular per-milestone client visibility
- PDF progress-report export
- On-image pin annotations

---

## Current Status (2026-08-08 → 2026-08-09)

### #1 Internal team collaboration — implemented, tests green, merged

Built on branch `004-team-collaboration` as `specs/004-team-collaboration/` (planning docs: [spec](specs/004-team-collaboration/spec.md), [research](specs/004-team-collaboration/research.md), [plan](specs/004-team-collaboration/plan.md), [data-model](specs/004-team-collaboration/data-model.md), [contracts](specs/004-team-collaboration/contracts/api.md), [tasks](specs/004-team-collaboration/tasks.md)).

- **Implementation**: complete — all 35 tasks in tasks.md checked (Phases 1–6).
- **Backend (new)**: migration `002_internal_collaboration.py` (`internal_notes`, `mentions`, `to_dos`); models `internal_note.py`, `todo.py`; schemas `internal_note.py`, `todo.py`; services `collaboration.py`, `internal_note.py`, `todo.py`; routes `collaborators.py`, `internal_notes.py`, `todos.py`. Modified: `ProjectMember.role` gains `collaborator`; `NotificationType` gains `mention`/`todo_assigned`; access-gate dependency factories in `dependencies.py`.
- **Real-time**: deviates slightly from plan — team-only broadcast implemented as `broadcast_to_project_team()` with an `_allow_user_ids` allowlist filter in `websocket/manager.py` (not `handlers.py`); client-role connections never receive internal events.
- **Frontend (new)**: `components/collaboration/` — `InternalPanel.tsx`, `CollaboratorList.tsx`, `InternalNoteList.tsx`, `TodoCard.tsx`; API clients `collaborators.ts`, `internalNotes.ts`, `todos.ts`; types, `notificationStore.ts` (mention/todo_assigned), `useWebSocket.ts`; `ProjectView.tsx` renders the internal panel only for owner/collaborators.
- **Verification**: backend `31 passed` (8 collaborators, 6 notes, 7 to-dos, 4 internal-visibility + pre-existing suites) via `backend/.venv`. Client-hiding enforced by shared access gate + serializer exclusion + WS allowlist. Frontend has no tests; `tsc` reports only pre-existing errors in untouched files (`client.ts`, `CommentThread.tsx`, `FileUploader.tsx`, `Header.tsx`, `useAuth.ts`, `Dashboard.tsx`, `Login.tsx`, `Register.tsx`).
- **Git state**: merged to `004-team-collaboration` as contextual gitmoji commits.

## Recommendation

Specs are single-feature. Pick one at a time:

1. **Next pick once #1 ships: #2 (file versioning)** — three existing edge
   cases already assume version history exists. This is now the next genuine gap.
2. **After that: #3 (client approvals / sign-offs)** — tangible go/no-go signal, natural
   extension of milestones + feedback.
3. **Cheap wins above the line: #4 (activity feed) and #5 (in-app notifications)** —
   small on top of existing events/Notification model.
