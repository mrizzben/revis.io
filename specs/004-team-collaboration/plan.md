# Implementation Plan: Internal Team Collaboration

**Branch**: `004-team-collaboration` | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-team-collaboration/spec.md`

## Summary

Add internal team collaboration to existing architect↔client projects: project owners add team members as **collaborators**, and the internal team shares **internal notes** (with `@mentions`), replies, and assignable/status-tracked **to-dos**. All internal content is scoped to project collaborators/owner and is **completely hidden from clients** via role-based authorization.

The existing `ProjectMember` table already models per-project membership with a `role` column (currently `"client"`). This feature introduces an internal role (`"collaborator"`), and three new content types — internal notes (with mentions/replies) and to-dos — plus in-app notifications for mentions and assignments reusing the existing `Notification` model and real-time WebSocket channel.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 + React 18 (frontend)  
**Primary Dependencies**: Existing (FastAPI async, SQLAlchemy 2.x async, pydantic v2, React Router, TanStack Query, Zustand, Tailwind CSS). No new runtime dependencies.  
**Storage**: PostgreSQL 16 — new tables: `internal_notes`, `internal_note_replies` (or threaded via `parent_id`), `mentions`, `to_dos`. Reuse existing `project_members`, `notifications`.  
**Testing**: pytest + httpx async (backend); Vitest + React Testing Library (frontend)  
**Target Platform**: Modern web browsers (Chrome, Firefox, Safari, Edge latest 2 versions); Linux server (Docker)  
**Project Type**: Web application (SPA frontend + REST backend + WebSockets) — backend-heavy feature with frontend UI  
**Performance Goals**: Internal note/to-do create-and-display <1s p95; real-time updates propagate to connected team members within 10s; happy-path page renders <1s.  
**Constraints**: Strict internal↔client authorization — internal content must never leak to client-facing routes/views; no new background jobs; reuse existing notification and WebSocket infrastructure.  
**Scale/Scope**: ~100 architects + collaborators, ~1000 projects, ~10k files; projected internal volume modest (thousands of notes/to-dos).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Ease of Use

| Criterion | Status | Evidence |
| ----------- | -------- | ---------- |
| Intuitive internal workspace | ✅ PASS | Collaborators/owner see a clearly separated internal panel (notes + to-dos) on the project page; visible collaborators with one-click add |
| Minimal cognitive load | ✅ PASS | Reuses existing project navigation; @mention picker and to-do creation are standard, discoverable patterns |
| Accessible terminology | ✅ PASS | Domain terms "collaborators", "internal note", "to-do", "mention" — plain language, no jargon |

### II. Reactive UI

| Criterion | Status | Evidence |
| ----------- | -------- | ---------- |
| Real-time state propagation | ✅ PASS | New notes, replies, mentions, and to-do status changes invalidate React Query cache and are broadcast via existing WebSocket channel to connected team members |
| Immediate visual feedback | ✅ PASS | Optimistic UI for note/to-do creation; to-do status toggle updates instantly with rollback on error |
| Dynamic, responsive interface | ✅ PASS | Internal panel live-updates as collaborators act; mention/assignee pickers filter as you type |

### III. Security

| Criterion | Status | Evidence |
| ----------- | -------- | ---------- |
| Authentication required | ✅ PASS | All new endpoints require `get_current_user`; internal-content endpoints additionally require project collaborator/owner access |
| Authorization scoped | ✅ PASS | Shared access gate: owner → full control; collaborator → read/write internal content; client → 403/404 and content never returned on project/client routes |
| Data protection | ✅ PASS | Internal content never serialized into client-facing payloads; mention and assignment notifications only to internal team |

**Gate Result**: ALL PASS — No violations.

**Post-Design Re-Check**: ALL PASS.

## Project Structure

### Documentation (this feature)

```text
specs/004-team-collaboration/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── project.py                # ProjectMember.role: add "collaborator"; helper access queries
│   │   ├── internal_note.py          # NEW — InternalNote, InternalNoteReply (or threaded), Mention
│   │   ├── todo.py                   # NEW — ToDo
│   │   └── notification.py           # Add NotificationType: mention, todo_assigned
│   ├── schemas/
│   │   ├── internal_note.py          # NEW — create/update/read + reply + mention DTOs
│   │   └── todo.py                   # NEW — create/update/read DTOs
│   ├── services/
│   │   ├── collaboration.py          # NEW — collaborator add/remove, shared internal-access gate
│   │   ├── internal_note.py          # NEW — CRUD, replies, mention resolution + notification fanout
│   │   └── todo.py                   # NEW — CRUD, assignment, status + notification fanout
│   ├── api/
│   │   ├── dependencies.py           # Add get_project_for_internal / get_project_for_owner helpers
│   │   ├── router.py                 # Register collaborators, internal-notes, to-dos
│   │   └── routes/
│   │       ├── collaborators.py      # NEW — add/remove/list collaborators
│   │       ├── internal_notes.py     # NEW — list/create/update/reply/mentions
│   │       └── todos.py              # NEW — list/create/update/assign/status
│   └── websocket/
│       ├── manager.py                # Add broadcast_to_project_team (user allowlist, excludes clients)
│       └── handlers.py               # Existing connection handling (unchanged)
│   └── migrations/versions/
│       └── 002_internal_collaboration.py  # NEW — add tables + role enum value + notification types
└── tests/
    ├── test_collaborators.py         # NEW
    ├── test_internal_notes.py        # NEW (incl. mention fanout)
    ├── test_todos.py                 # NEW
    └── test_internal_visibility.py   # NEW — client must never see internal content

frontend/
├── src/
│   ├── api/
│   │   └── endpoints/
│   │       ├── collaborators.ts      # NEW — CRUD collaborators
│   │       ├── internalNotes.ts      # NEW — CRUD notes/replies/mentions
│   │       └── todos.ts              # NEW — CRUD to-dos + status
│   ├── components/
│   │   └── collaboration/
│   │       ├── InternalPanel.tsx     # NEW — container (notes + to-dos), internal-only
│   │       ├── CollaboratorList.tsx  # NEW — add/remove collaborators
│   │       ├── InternalNoteList.tsx  # NEW — list/reply + note form with @mention picker (merged)
│   │       └── TodoCard.tsx          # NEW — assignee, status toggle
│   ├── pages/
│   │   └── ProjectView.tsx           # Render InternalPanel only for team members
│   ├── stores/
│   │   └── notificationStore.ts      # Consume new mention/todo notification types
│   └── types/
│       └── index.ts                  # InternalNote, ToDo, Mention, Collaborator types
```

**Structure Decision**: Backend-heavy feature following existing layered architecture (`models/` → `services/` → `api/routes/`), mirroring the existing `comments`/`milestones` feature slices. Frontend adds a collaboration-focused component subtree under `components/collaboration/`, gated in `ProjectView.tsx` by internal role. New entities, routes, and tests all follow established patterns.

## Complexity Tracking

> No Constitution violations — Complexity Tracking section is not required.
