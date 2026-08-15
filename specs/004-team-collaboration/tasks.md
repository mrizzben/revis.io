# Tasks: Internal Team Collaboration

**Input**: Design documents from `/specs/004-team-collaboration/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included only where they secure a safety-critical guarantee (client-hiding) — required because this feature rests on role-based content isolation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Web app: `backend/src/`, `frontend/src/`, `backend/tests/`, `frontend/src/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Migration scaffold shared by all stories. Backend and frontend codebases already exist; this feature adds new tables/routes/components.

- [X] T001 Add migration `002_internal_collaboration.py` in backend/migrations/versions/ creating `internal_notes`, `mentions`, `to_dos` tables per data-model.md
- [X] T002 [P] Add `collaborator` to `ProjectMember.role` handling and `mention`/`todo_assigned` to `NotificationType` enum in backend/src/models/project.py and backend/src/models/notification.py
- [X] T003 Add internal-access dependency factories (`require_project_collaborator`, `require_project_owner`) in backend/src/api/dependencies.py reusing `get_current_user`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared internal-access gate and membership plumbing that ALL user stories depend on. No story work begins until complete.

**⚠️ CRITICAL**: The internal-team access gate is the single point enforcing "hidden from clients" — every story builds on it.

- [X] T004 [P] Add `get_internal_project` / internal-membership access check helper (owner or collaborator, else 404) in backend/src/services/collaboration.py, used by all internal routes
- [X] T005 Add base pydantic schemas for internal notes, mentions, and to-dos in backend/src/schemas/internal_note.py and backend/src/schemas/todo.py
- [X] T006 Register `collaborators`, `internal_notes`, `todos` routers in backend/src/api/router.py
- [X] T007 [P] Add internal-note and to-do event broadcast (team-only, clients excluded) in backend/src/websocket/handlers.py

**Checkpoint**: Foundation ready — internal access gate + route scaffolding in place. User story implementation can begin.

---

## Phase 3: User Story 1 - Add Internal Collaborators (Priority: P1) 🎯 MVP

**Goal**: Project owner adds/removes team members as collaborators; collaborators access the project's internal workspace; clients never see the collaborator surface.

**Independent Test**: Owner adds a teammate to a project; the teammate opens the project and sees the internal workspace, while a client on the same project sees no collaborator/workspace trace.

### Implementation for User Story 1

- [X] T008 [P] [US1] Add `collaborator` role support in ProjectMember query/creation helpers in backend/src/services/collaboration.py
- [X] T009 [US1] Implement add/remove/list collaborator logic (owner-only; idempotent add; immediate revoke) in backend/src/services/collaboration.py
- [X] T010 [US1] Implement collaborators routes in backend/src/api/routes/collaborators.py per contracts/api.md (GET/POST/DELETE `/api/projects/{id}/collaborators...`)
- [X] T011 [P] [US1] Add collaborator API client in frontend/src/api/endpoints/collaborators.ts
- [X] T012 [US1] Build CollaboratorList.tsx (add/remove collaborators) and Collaborator* types in frontend/src/components/collaboration/CollaboratorList.tsx and frontend/src/types/index.ts
- [X] T013 [US1] Render InternalPanel.tsx in frontend/src/pages/ProjectView.tsx only for owner/collaborator (client sees nothing)
- [X] T014 [US1] Backend visibility test: client role calling collaborators/internal endpoints gets 404, and collaborator surface absent from client project payload in backend/tests/test_internal_visibility.py

**Checkpoint**: US1 fully functional and testable independently (owner adds collaborator; collaborator enters internal workspace; client unaffected).

---

## Phase 4: User Story 2 - Internal Notes with @Mentions (Priority: P2)

**Goal**: Collaborators create internal notes with `@mentions`; mentioned members get notified and can reply; all hidden from clients.

**Independent Test**: A collaborator posts an internal note mentioning another collaborator; the named member receives a notification and replies; a client sees none of the notes/mentions.

### Implementation for User Story 2

- [X] T015 [P] [US2] Create `InternalNote` and `Mention` models in backend/src/models/internal_note.py per data-model.md (project_id, author_id, parent_id self-ref, body + mentions join)
- [X] T016 [US2] Implement note/reply/mention services (create, list, reply, mention fan-out via Notification type `mention`) in backend/src/services/internal_note.py
- [X] T017 [US2] Implement internal-notes routes in backend/src/api/routes/internal_notes.py per contracts/api.md (GET/POST notes, POST replies)
- [X] T018 [P] [US2] Add internal-notes API client in frontend/src/api/endpoints/internalNotes.ts
- [X] T019 [P] [US2] Add `mention` notification handling + consumption in frontend/src/stores/notificationStore.ts
- [X] T020 [P] [US2] Build InternalNoteList.tsx and InternalNoteForm.tsx (with `@mention` picker) in frontend/src/components/collaboration/
- [X] T021 [US2] Wire notes into InternalPanel.tsx (create/list/reply, mention picker) in frontend/src/components/collaboration/InternalPanel.tsx
- [X] T022 [US2] Mention fan-out test: posting an @mention notifies the target, note+replies invisible in client payload in backend/tests/test_internal_notes.py and backend/tests/test_internal_visibility.py

**Checkpoint**: US1 AND US2 work independently — internal notes/mentions/replies flow among the team while clients remain clean.

---

## Phase 5: User Story 3 - Assignable and Tracked To-Dos (Priority: P3)

**Goal**: Collaborators create to-dos, assign them to teammates, mark complete; team tracks progress; hidden from clients.

**Independent Test**: A collaborator creates a to-do assigned to a teammate who marks it complete; the client never sees to-dos or their status.

### Implementation for User Story 3

- [X] T023 [P] [US3] Create `ToDo` model in backend/src/models/todo.py per data-model.md (project_id, assignee_id, status, created_by)
- [X] T024 [US3] Implement to-do services (create, update, assign, status, delete; assignment/completion notification type `todo_assigned`) in backend/src/services/todo.py
- [X] T025 [US3] Implement to-dos routes in backend/src/api/routes/todos.py per contracts/api.md (GET/POST, PATCH, DELETE `/api/projects/{id}/todos...`)
- [X] T026 [P] [US3] Add to-dos API client in frontend/src/api/endpoints/todos.ts
- [X] T027 [P] [US3] Build TodoCard.tsx (assignee, status toggle) in frontend/src/components/collaboration/TodoCard.tsx
- [X] T028 [US3] Wire to-dos into InternalPanel.tsx (create/assign/toggle) in frontend/src/components/collaboration/InternalPanel.tsx
- [X] T029 [US3] To-do tests: create/assign/status change notifies assignee; to-dos invisible in client payload in backend/tests/test_todos.py and backend/tests/test_internal_visibility.py

**Checkpoint**: US1, US2 AND US3 work — full internal collaboration loop (collaborators, notes/mentions, to-dos) with clients fully isolated.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening and consistency across the internal collaboration surface.

- [X] T030 Remove-collaborator edge case: reassign/handle open to-dos and surface mentions to owner on removal in backend/src/services/collaboration.py
- [X] T031 Empty states and invalid-input UX for internal panel (no collaborators, no notes, no to-dos; mention of non-collaborator) in frontend/src/components/collaboration/
- [X] T032 Sanitize note/to-do body text via existing sanitize helper (backend/src/core/sanitize.py) in note/todo services
- [X] T033 Run full backend test suite in backend/tests/ and frontend `npm test` to confirm no regressions
- [X] T034 [P] Add real-time/notification latency verification: @mention and to-do assignment notification and internal-content propagation reach a connected team member within 10s (SC-003, SC-005) via backend/tests/ (timed integration assertions)
- [X] T035 Update quickstart.md (specs/004-team-collaboration/quickstart.md) if setup/manual-verification details changed during implementation

**Checkpoint**: Feature complete, security guarantees verified, no regressions.

---

## Dependencies

- **Phase 1 → Phase 2 → { Phase 3, Phase 4, Phase 5 } → Phase 6**
- US1 (Phase 3) is the MVP prerequisite; US2 and US3 depend on the Phase 2 gate but are otherwise independent of each other.

### Parallel Execution by Story

- **US1**: T008, T011, T014 parallelizable (services/API client/types + visibility test);
- **US2**: T015, T018, T019, T020 parallelizable (model + frontend pieces) before T016/T017/T021/T022;
- **US3**: T023, T026, T027 parallelizable (model + frontend pieces) before T024/T025/T028/T029;
- Cross-story: US2 and US3 model/frontend work can proceed in parallel once Phase 2 gate is complete.

## Implementation Strategy

- **MVP scope**: Phase 1 + Phase 2 + Phase 3 (User Story 1) only — owner adds collaborators, collaborators access the internal workspace, clients isolated. Delivers the core "collaborate internally" foundation first.
- Add US2 (notes/@mentions) then US3 (to-dos) as incremental, independently-testable increments.
- Security verification (`test_internal_visibility.py`) is carried through every story phase to keep the client-hiding guarantee continuously intact.
