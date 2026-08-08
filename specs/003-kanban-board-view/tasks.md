# Tasks: Kanban Board View

**Input**: Design documents from `/specs/003-kanban-board-view/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted — add them if TDD is desired.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Install drag-and-drop dependency

- [x] T001 Install @dnd-kit packages (@dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities) in frontend/package.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend endpoint + frontend API function needed for drag-and-drop reassignment

**CRITICAL**: No drag-and-drop functionality works until this phase is complete

- [x] T002 Add PATCH /files/{file_id} route in backend/src/api/routes/files.py — accepts milestone_id, validates milestone belongs to project, updates file record, broadcasts file_updated via WebSocket
- [x] T003 Add updateFileMilestone(fileId, milestoneId) API function in frontend/src/api/endpoints/files.ts
- [x] T004 Add UpdateFileMilestoneRequest type to frontend/src/types/index.ts

**Checkpoint**: Foundation ready — PATCH endpoint exists, frontend can call it.

---

## Phase 3: User Story 1 - Architect Views Project as Kanban Board (Priority: P1)

**Goal**: Kanban board renders milestones as columns and files as cards. Architects can drag cards between columns to reassign milestones.

**Independent Test**: Open a project with 2+ milestones each containing files → toggle to board view → see columns with cards → drag a card to another column → card stays in new column on page reload.

### Implementation for User Story 1

- [x] T005 [P] [US1] Create KanbanCard component (thumbnail, filename, file type badge, version number, draggable with @dnd-kit useSortable) in frontend/src/components/project/KanbanCard.tsx
- [x] T006 [P] [US1] Create KanbanColumn component (milestone name header, completion badge, empty state, droppable with @dnd-kit useDroppable) in frontend/src/components/project/KanbanColumn.tsx
- [x] T007 [US1] Create KanbanBoard component — fetches milestones and project files via TanStack Query, renders DndContext with horizontal scroll, maps milestones to sorted columns, handles onDragEnd to call updateFileMilestone mutation in frontend/src/components/project/KanbanBoard.tsx
- [x] T008 [US1] Add KanbanBoard import and render section to ProjectManage page (below stats bar, between milestones and file uploader sections) in frontend/src/pages/ProjectManage.tsx

**Checkpoint**: Board renders with columns and cards. Drag-and-drop reassigns milestone_id. Card snaps back on error.

---

## Phase 4: User Story 2 - Architect Toggles Between Timeline and Board View (Priority: P2)

**Goal**: View toggle (Board / Timeline) in the project management page switches between the milestone timeline view and the kanban board view.

**Independent Test**: Open project management page → see timeline by default → click "Board" toggle → see board with columns → click "Timeline" → see timeline again.

### Implementation for User Story 2

- [x] T009 [US2] Add viewMode state ('timeline' | 'board') and view toggle buttons/segmented control between milestones header and content area in frontend/src/pages/ProjectManage.tsx
- [x] T010 [US2] Conditionally render MilestoneTimeline or KanbanBoard based on viewMode state in frontend/src/pages/ProjectManage.tsx

**Checkpoint**: Toggle switches between timeline and board. Default view is timeline.

---

## Phase 5: User Story 3 - Client Views Project as Read-Only Board (Priority: P3)

**Goal**: Clients can see the board view but cannot drag cards. Clicking a card opens the file viewer.

**Independent Test**: Log in as client → open project → toggle to board → see columns and cards → attempt to drag card → card does not move → click card → file viewer opens.

### Implementation for User Story 3

- [x] T011 [US3] Pass user role from auth store to KanbanBoard; disable drag on cards when role is 'client' (render plain div instead of @dnd-kit sortable) in frontend/src/components/project/KanbanBoard.tsx and frontend/src/components/project/KanbanCard.tsx
- [x] T012 [US3] Wire card click to file viewer navigation (reuse existing file preview behavior from timeline view) in frontend/src/components/project/KanbanCard.tsx

**Checkpoint**: Clients see the board in read-only mode. Drag is disabled. Click opens file preview.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Empty states, error states, edge case handling

- [x] T013 Handle empty state — project with no milestones shows "Create milestones to use the board view" message in KanbanBoard component in frontend/src/components/project/KanbanBoard.tsx
- [x] T014 Handle empty state — milestone with no files shows "No files in this milestone" message in KanbanColumn component in frontend/src/components/project/KanbanColumn.tsx
- [x] T015 Handle long milestone names — truncate with ellipsis and show full name on hover tooltip in KanbanColumn component in frontend/src/components/project/KanbanColumn.tsx
- [x] T016 Handle drag failure — card snaps back to original position with error toast in frontend/src/components/project/KanbanBoard.tsx
- [x] T017 Verify Constitution compliance: confirm ease of use (board toggle is single click), reactive UI (drag-drop instant feedback), security (clients cannot move cards) per .specify/memory/constitution.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS drag-and-drop in US1
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) for PATCH endpoint + API function
- **User Story 2 (Phase 4)**: Depends on US1 (Phase 3) for KanbanBoard component (toggle needs a component to switch to)
- **User Story 3 (Phase 5)**: Depends on US1 (Phase 3) for KanbanBoard + KanbanCard components
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). No dependencies on other stories.
- **User Story 2 (P2)**: Can start after US1 (Phase 3) — needs KanbanBoard component to exist for toggle to have something to show.
- **User Story 3 (P3)**: Can start after US1 (Phase 3) — needs KanbanBoard + KanbanCard to exist.

### Within Each User Story

- Frontend components marked [P] can be built in parallel
- Components imported into pages after all child components exist

### Parallel Opportunities

- **Phase 3 (US1)**: T005, T006 (KanbanCard, KanbanColumn) can run in parallel. T007 (KanbanBoard) depends on both. T008 (ProjectManage import) depends on T007.

---

## Parallel Example: User Story 1

```bash
# Phase 3 components — both independent, launch together:
Task: "T005 Create KanbanCard component in frontend/src/components/project/KanbanCard.tsx"
Task: "T006 Create KanbanColumn component in frontend/src/components/project/KanbanColumn.tsx"

# After T005, T006:
Task: "T007 Create KanbanBoard component in frontend/src/components/project/KanbanBoard.tsx"

# After T007:
Task: "T008 Add KanbanBoard to ProjectManage page in frontend/src/pages/ProjectManage.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — install @dnd-kit
2. Complete Phase 2: Foundational — PATCH endpoint + API function
3. Complete Phase 3: User Story 1 — board with drag-and-drop
4. **STOP and VALIDATE**: Create milestones → upload files → switch to board → drag cards → verify persistence
5. Deploy/demo MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Board with drag-and-drop (MVP!)
3. Add User Story 2 → View toggle
4. Add User Story 3 → Client read-only board
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Complete Setup + Foundational together
2. Once Foundational is complete:
   - **Developer A**: User Story 1 (Phase 3) — board components + drag-and-drop
   - **Developer B**: User Story 2 (Phase 4) — view toggle (needs US1 board component)
   - **Developer C**: User Story 3 (Phase 5) — client read-only (needs US1 cards)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable per its Independent Test criteria
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- @dnd-kit must be installed before any board component work begins
- PATCH endpoint must exist before drag-and-drop can persist changes
- The existing MilestoneTimeline component is untouched — it remains the default view
- Constitution compliance check (T017) covers all three principles: Ease of Use, Reactive UI, Security