# Implementation Plan: Architect-Client Design Portal

**Branch**: `001-architect-client-portal` | **Date**: 2026-05-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-architect-client-portal/spec.md`

## Summary

A real-time web application where architects present design files to clients, track milestone progress, and receive client feedback. Architects create projects, upload design files (CAD, PDF, images, 3D models) to S3, and invite clients via email. Clients view designs in near real-time as the architect updates files, with milestone tracking and contextual commenting. Firm accounts provide organizational ownership and project reassignment.

## Technical Context

**Language/Version**: Backend: Python 3.12; Frontend: TypeScript 5 + React 18
**Primary Dependencies**: FastAPI (async HTTP + WebSockets), SQLAlchemy 2.x (async ORM), boto3 (S3), React Router 6, Zustand (state), TanStack Query (server state), Tailwind CSS
**Storage**: PostgreSQL 16 (metadata, users, projects, milestones, comments) + S3-compatible object storage (design files and thumbnails)
**Testing**: Backend: pytest + httpx (async); Frontend: Vitest + React Testing Library
**Target Platform**: Modern web browsers (Chrome, Firefox, Safari, Edge latest 2 versions); Linux server (Docker containers)
**Project Type**: Web application (SPA frontend + REST + WebSocket backend)
**Performance Goals**: 500 concurrent users, real-time file update propagation <10 seconds, API p95 latency <200ms
**Constraints**: File uploads up to 1GB via presigned S3 URLs, thumbnail generation <30s, initial deployment ≤100GB stored files
**Scale/Scope**: ~100 architects, ~400 clients, ~1000 projects, ~10k design files initially

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Ease of Use
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Intuitive onboarding | ✅ PASS | Spec requires <5min project setup (SC-001); <3min client onboarding (SC-002) |
| Minimal cognitive load | ✅ PASS | Spec requires unified dashboards (FR-016); 90% task completion without help docs (SC-005) |
| Accessible terminology | ✅ PASS | UX uses domain language: "projects", "milestones", "design files" |

### II. Reactive UI
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Real-time state propagation | ✅ PASS | React + WebSocket push for file updates within 10s (FR-007, SC-003) |
| Immediate visual feedback | ✅ PASS | Upload progress indicators (FR-017); milestone completion visual markers (FR-010) |
| Dynamic, responsive interface | ✅ PASS | Zustand reactive stores + TanStack Query cache invalidation; Tailwind responsive design |

### III. Security
| Criterion | Status | Evidence |
|-----------|--------|----------|
| Authentication required | ✅ PASS | Email/password + SSO accounts (FR-001); mandatory client account creation (FR-006) |
| Authorization scoped | ✅ PASS | Client access restricted to invited projects only (FR-015); firm-based RBAC (FR-021, FR-022) |
| Data protection | ✅ PASS | S3 presigned URLs (no direct file access); HTTPS enforced; password hashing; invitation link expiry |
| Session management | ✅ PASS | 24h session duration with extend option; token-based auth for WebSocket connections |

**Gate Result (Pre-Design)**: ALL PASS — No violations.

**Post-Design Re-Check**: ALL PASS. Data model enforces RBAC (firm-scoped ownership, project_members), API contracts secure all endpoints with bearer JWT, WebSocket auth via query token, presigned S3 URLs with server-side validation. No constitution violations introduced by the design.

## Project Structure

### Documentation (this feature)

```text
specs/001-architect-client-portal/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI 3.1 specification
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   ├── dependencies.py   # Auth dependency injection
│   │   ├── router.py         # API router aggregation
│   │   └── routes/
│   │       ├── auth.py       # Auth endpoints
│   │       ├── projects.py   # Project CRUD + invitations
│   │       ├── files.py      # File upload/download/presigned URLs
│   │       ├── milestones.py # Milestone CRUD
│   │       └── comments.py   # Comments CRUD + WebSocket
│   ├── core/
│   │   ├── config.py         # App settings (env vars)
│   │   ├── security.py       # JWT, password hashing
│   │   └── database.py       # Async SQLAlchemy engine + session
│   ├── models/
│   │   ├── base.py           # Declarative base
│   │   ├── user.py           # User + Firm models
│   │   ├── project.py        # Project + Invitation models
│   │   ├── file.py           # DesignFile + FileVersion models
│   │   ├── milestone.py      # Milestone model
│   │   └── comment.py        # Comment model
│   ├── schemas/
│   │   ├── user.py           # Pydantic request/response schemas
│   │   ├── project.py
│   │   ├── file.py
│   │   ├── milestone.py
│   │   └── comment.py
│   ├── services/
│   │   ├── auth.py           # Registration, login, token refresh
│   │   ├── project.py        # Project business logic
│   │   ├── file.py           # S3 upload/download, thumbnail generation
│   │   ├── milestone.py      # Milestone management
│   │   ├── comment.py        # Comment + notification logic
│   │   └── notification.py   # Email + WebSocket push
│   ├── websocket/
│   │   ├── manager.py        # Connection manager with project rooms
│   │   └── handlers.py       # Event handlers (file_update, comment_added)
│   └── main.py               # FastAPI app entry point
├── migrations/               # Alembic migrations
├── tests/
│   ├── api/                  # HTTP endpoint tests
│   ├── services/             # Service unit tests
│   └── conftest.py           # Async fixtures (DB, S3 mock, test client)
├── Dockerfile
├── requirements.txt
└── alembic.ini

frontend/
├── src/
│   ├── api/
│   │   ├── client.ts         # Axios/fetch wrapper with auth interceptor
│   │   └── endpoints/        # Typed API endpoint functions
│   ├── components/
│   │   ├── ui/               # Shared UI primitives (Button, Modal, Input)
│   │   ├── layout/           # App shell, sidebar, header
│   │   ├── project/          # Project-specific components
│   │   ├── file/             # File uploader, file preview, file list
│   │   ├── milestone/        # Milestone timeline, milestone card
│   │   └── comment/          # Comment thread, comment form
│   ├── hooks/
│   │   ├── useWebSocket.ts   # WebSocket connection + reconnection
│   │   ├── useAuth.ts        # Auth state + actions
│   │   └── useFileUpload.ts   # Multipart + presigned upload hook
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Register.tsx
│   │   ├── Dashboard.tsx     # Architect or client unified dashboard
│   │   ├── ProjectView.tsx   # Client-facing project view
│   │   ├── ProjectManage.tsx # Architect project management
│   │   └── InvitationAccept.tsx
│   ├── stores/
│   │   ├── authStore.ts      # Zustand auth store
│   │   └── notificationStore.ts
│   ├── types/
│   │   └── index.ts          # Shared TypeScript types
│   ├── App.tsx
│   └── main.tsx
├── tests/
│   ├── components/
│   ├── hooks/
│   └── setup.ts
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── package.json

docker-compose.yml            # PostgreSQL + MinIO (S3 dev) + backend + frontend
```

**Structure Decision**: Web application with separate `backend/` and `frontend/` directories. Backend uses a service-layer architecture (routes → services → models). Frontend uses a feature-grouped component structure with centralized API client and WebSocket connection management.

## Complexity Tracking

> No Constitution violations to justify.