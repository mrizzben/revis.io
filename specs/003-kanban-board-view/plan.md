# Implementation Plan: Kanban Board View

**Branch**: `003-kanban-board-view` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-kanban-board-view/spec.md`

## Summary

A kanban board view for the project management page that renders existing milestones as columns and design files as drag-and-drop cards. Architects reassign files between milestones by dragging cards. Clients see a read-only board. No new data models, no schema changes.

**One minimal backend addition**: A PATCH endpoint on files to update `milestone_id` (required for drag-and-drop reassignment).

## Technical Context

**Language/Version**: TypeScript 5 + React 18 (frontend); Python 3.12 (backend)  
**Primary Dependencies**: Existing (React, TanStack Query, Tailwind CSS, Zustand). Add a lightweight drag-and-drop library or use HTML5 native DnD.  
**Storage**: N/A — no new storage  
**Testing**: Vitest + React Testing Library (frontend); pytest + httpx (backend for the new PATCH endpoint)  
**Target Platform**: Modern web browsers (Chrome, Firefox, Safari, Edge latest 2 versions)  
**Project Type**: Web application (SPA frontend + REST backend) — frontend-only feature with one backend endpoint  
**Performance Goals**: Drag-and-drop feels instant (<100ms UI feedback), board renders in <1s for projects with up to 50 files across 10 milestones.  
**Constraints**: Must use existing milestone and file API data. Zero schema changes. No new database tables. No new background jobs.  
**Scale/Scope**: Up to 1000 files across 20 milestones per project on the board.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Ease of Use
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Intuitive visualization | ✅ PASS | Kanban board is a universally recognized pattern; milestones-as-columns and files-as-cards require no training |
| Minimal cognitive load | ✅ PASS | Single toggle (Board/Timeline) to switch views; drag-and-drop is natural for file reassignment |
| Accessible terminology | ✅ PASS | Uses existing domain language: "milestones", "files" — no new jargon |

### II. Reactive UI
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Real-time state propagation | ✅ PASS | Drag-drop calls PATCH endpoint then invalidates React Query cache; WebSocket events from other users trigger board re-render |
| Immediate visual feedback | ✅ PASS | Card moves on drop before server confirms; error snaps card back with toast notification |
| Dynamic, responsive interface | ✅ PASS | Horizontal scroll for many columns; empty states for milestones with no files |

### III. Security
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Authentication required | ✅ PASS | Existing auth middleware on new PATCH endpoint; only architects can move cards |
| Authorization scoped | ✅ PASS | Existing project access checks reused; clients see board but drag is disabled |
| Data protection | ✅ PASS | No new data storage; milestone_id update via existing file records |

**Gate Result**: ALL PASS — No violations.

**Post-Design Re-Check**: ALL PASS.

## Project Structure

### Documentation (this feature)

```text
specs/003-kanban-board-view/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # N/A — no new entities
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── routes/
│   │       └── files.py              # Add PATCH /files/{file_id} (update milestone_id)

frontend/
├── src/
│   ├── api/
│   │   └── endpoints/
│   │       └── files.ts              # Add updateFileMilestone() API call
│   ├── components/
│   │   └── project/
│   │       └── KanbanBoard.tsx       # NEW — board view component
│   │       └── KanbanColumn.tsx      # NEW — single milestone column
│   │       └── KanbanCard.tsx        # NEW — single file card
│   ├── pages/
│   │   └── ProjectManage.tsx          # Add Board/Timeline view toggle
│   └── types/
│       └── index.ts                  # Add update request type if needed
```

**Structure Decision**: Frontend-only feature with one minimal backend endpoint. New components follow existing patterns in `frontend/src/components/project/`. The board view reuses existing `FileList` thumbnail and file card patterns.

## Complexity Tracking

> No Constitution violations — Complexity Tracking section is not required.