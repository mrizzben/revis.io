# Tasks: Architect-Client Design Portal

**Input**: Design documents from `/specs/001-architect-client-portal/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted — add them if TDD is desired.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, Docker services, and basic tooling

- [x] T001 Create docker-compose.yml with PostgreSQL 16, Redis 7, MinIO (S3 dev), backend, and frontend services
- [x] T002 [P] Initialize backend Python project with FastAPI, uvicorn, SQLAlchemy 2.x, alembic, boto3, pwdlib, PyJWT, arq, resend dependencies in backend/requirements.txt and backend/Dockerfile
- [x] T003 [P] Initialize frontend Vite + React 18 + TypeScript 5 project with package.json, vite.config.ts, index.html, tailwind.config.ts, tsconfig.json, postcss.config.js in frontend/
- [x] T004 [P] Configure backend environment variables (SECRET_KEY, DATABASE_URL, REDIS_URL, S3 settings, RESEND_API_KEY, FRONTEND_URL, token expiry) in backend/.env.example and backend/src/core/config.py
- [x] T005 [P] Configure frontend Tailwind CSS (design tokens, colors, typography) and global styles in frontend/src/index.css and frontend/tailwind.config.ts
- [x] T006 [P] Configure backend linting (ruff) in backend/pyproject.toml and frontend linting/formatting (prettier, eslint) in frontend/.eslintrc.cjs and frontend/.prettierrc

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Run Alembic init and create initial migration with all 11 tables (users, firms, projects, project_members, invitations, milestones, design_files, file_versions, comments, email_verifications, password_resets) using DDL and indexes from data-model.md in backend/migrations/
- [x] T008 [P] Implement JWT access/refresh token creation and validation, password hashing with pwdlib (Argon2) in backend/src/core/security.py
- [x] T009 [P] Implement async SQLAlchemy engine, session factory, declarative Base, and get_db dependency in backend/src/core/database.py and backend/src/models/base.py
- [x] T010 [P] Create FastAPI app entry point with CORS (FRONTEND_URL), global exception handlers, and API router aggregation in backend/src/main.py and backend/src/api/router.py
- [x] T011 [P] Implement auth dependency injection (get_current_user from Bearer JWT, require_role for architect/client) in backend/src/api/dependencies.py
- [x] T012 [P] Create frontend API client (axios instance with baseURL, Bearer token request interceptor, 401 auto-refresh response interceptor with request queuing) in frontend/src/api/client.ts
- [x] T013 [P] Create Zustand auth store with persist middleware (access_token, user profile, login/logout/setUser actions, isAuthenticated computed) in frontend/src/stores/authStore.ts
- [x] T014 [P] Build app shell layout components (AppLayout with sidebar navigation, Header with user dropdown, protected route wrapper requiring auth) in frontend/src/components/layout/
- [x] T015 [P] Set up React Router 6 routing (public routes: login/register/invitation-accept, protected routes: dashboard/project) in frontend/src/App.tsx
- [x] T016 [P] Configure boto3 S3/MinIO client with endpoint, credentials, bucket auto-create on startup in backend/src/services/file.py (client initialization section)
- [x] T017 [P] Set up Resend email client with async context manager and EMAIL_FROM config in backend/src/services/notification.py
- [x] T018 [P] Define shared TypeScript interfaces matching all API response schemas (User, Firm, Project, DesignFile, Milestone, Comment, Invitation) in frontend/src/types/index.ts
- [x] T019 [P] Build shared UI primitives (Button, Modal, Input/TextArea, Card, Badge, Spinner, ProgressBar, Toast/notification) in frontend/src/components/ui/

**Checkpoint**: Foundation ready — database, auth, API client, app shell all operational. User story implementation can now begin.

---

## Phase 3: User Story 1 - Architect Creates Project and Uploads Designs (Priority: P1) 🎯 MVP

**Goal**: Architect can sign up, create a project, upload design files with previews, invite clients via email, and manage their firm. Clients can register via invitation and access the project.

**Independent Test**: Register as architect → create project → upload design files (PNG, PDF, DWG) → verify thumbnails generated → invite client by email → open invitation link → register as client → verify access to project files.

### Models for User Story 1

- [ ] T020 [P] [US1] Create User, Firm, EmailVerification, and PasswordReset SQLAlchemy models in backend/src/models/user.py
- [ ] T021 [P] [US1] Create Project, ProjectMember, and Invitation SQLAlchemy models in backend/src/models/project.py
- [ ] T022 [P] [US1] Create DesignFile and FileVersion SQLAlchemy models with thumbnail_status enum in backend/src/models/file.py

### Schemas for User Story 1

- [ ] T023 [P] [US1] Create Pydantic schemas for auth (RegisterRequest, LoginRequest, TokenResponse, UserResponse, ForgotPasswordRequest, ResetPasswordRequest) in backend/src/schemas/user.py
- [ ] T024 [P] [US1] Create Pydantic schemas for projects and invitations (ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse, InvitationResponse) in backend/src/schemas/project.py
- [ ] T025 [P] [US1] Create Pydantic schemas for files (FileUploadUrlRequest, FileUploadUrlResponse, MultipartInitiateRequest, MultipartPartUrlsRequest, MultipartCompleteRequest, DesignFileResponse) in backend/src/schemas/file.py

### Services for User Story 1

- [ ] T026 [US1] Implement AuthService (register architect/client with email verification, login with access+refresh tokens, refresh token rotation, logout, forgot/reset password, verify email) in backend/src/services/auth.py
- [ ] T027 [US1] Implement ProjectService (CRUD with owner/firm validation, archive, list by user role, firm-scoped queries, project deletion cascade) in backend/src/services/project.py
- [ ] T028 [US1] Implement FileService (presigned upload URL generation with content-type enforcement, file record creation with UUID S3 key, soft delete, presigned download URL generation, file listing with milestone filter) in backend/src/services/file.py
- [ ] T029 [US1] Implement InvitationService (create invitation with url-safe token + 7-day expiry, validate invitation token, mark as used on client registration, resend with token replacement) in backend/src/services/project.py
- [ ] T030 [US1] Implement FirmService (create firm with founding admin, list firm members, add architect to firm by email) in backend/src/services/project.py
- [ ] T031 [US1] Implement NotificationService (send invitation email with Resend, send welcome/verification emails, send password reset email, create in-app notification records) in backend/src/services/notification.py

### Routes for User Story 1

- [ ] T032 [US1] Implement auth routes (POST /api/auth/register, login, refresh, logout, forgot-password, reset-password, verify-email/{token}) in backend/src/api/routes/auth.py
- [ ] T033 [US1] Implement project routes (GET/POST /api/projects, GET/PATCH/DELETE /api/projects/{project_id}) in backend/src/api/routes/projects.py
- [ ] T034 [US1] Implement file upload routes (POST /api/files/upload-url, multipart/initiate, multipart/{upload_id}/part-urls, multipart/{upload_id}/complete, multipart/{upload_id}/abort, POST /api/files/{file_id}/upload-complete, GET/DELETE /api/files/{file_id}, GET /api/files/{file_id}/download) in backend/src/api/routes/files.py
- [ ] T035 [US1] Implement invitation routes (POST /api/projects/{project_id}/invite, GET /api/invitations/{token}) in backend/src/api/routes/projects.py
- [ ] T036 [US1] Implement firm routes (POST/GET /api/firms, GET/POST /api/firms/{firm_id}/members) and user profile route (GET /api/users/me) in backend/src/api/routes/firms.py

### Thumbnail Processing for User Story 1

- [ ] T037 [US1] Implement ARQ thumbnail worker setup (WorkerSettings with Redis connection, job timeout 120s for DWG/IFC, 30s others, 3 retries with exponential backoff, job dedup key) in backend/src/services/thumbnail.py
- [ ] T038 [US1] Implement thumbnail generation service (Pillow for raster, PyMuPDF for PDF page 1 render, ezdxf+matplotlib for DXF, trimesh for 3D snapshots, WebP output at small 200x200 and medium 600x600) in backend/src/services/thumbnail.py
- [ ] T039 [US1] Implement 3D preview generation (IfcOpenShell+trimesh for IFC→glTF, trimesh for OBJ/STL→glTF conversion) in backend/src/services/thumbnail.py
- [ ] T040 [US1] Wire upload-complete callback and multipart-complete to enqueue thumbnail ARQ job, update thumbnail_status state machine (pending→processing→complete/failed/unsupported) in backend/src/services/file.py

### Frontend for User Story 1

- [ ] T041 [P] [US1] Create typed API endpoint functions for auth (register, login, refresh, logout, forgotPassword, resetPassword, verifyEmail, getMe) in frontend/src/api/endpoints/auth.ts
- [ ] T042 [P] [US1] Create typed API endpoint functions for projects (listProjects, createProject, getProject, updateProject, deleteProject) and invitations (inviteClient, getInvitation) in frontend/src/api/endpoints/projects.ts
- [ ] T043 [P] [US1] Create typed API endpoint functions for files (getUploadUrl, initiateMultipart, getPartUrls, completeMultipart, abortMultipart, uploadComplete, getFile, deleteFile, getDownloadUrl, getThumbnailUrl) and firms (createFirm, listFirms, getFirmMembers, addFirmMember) in frontend/src/api/endpoints/files.ts
- [ ] T044 [P] [US1] Build Login page with email/password form, validation, error display, and redirect after login in frontend/src/pages/Login.tsx
- [ ] T045 [P] [US1] Build Register page with email/password/name/role form, client invitation token handling, and redirect after registration in frontend/src/pages/Register.tsx
- [ ] T046 [P] [US1] Build InvitationAccept page that loads invitation details (project name, invited by) and prompts client to register via invitation token in frontend/src/pages/InvitationAccept.tsx
- [ ] T047 [US1] Implement useAuth hook (login, register, logout actions, session restore from persisted token, user profile fetch, loading/error states) in frontend/src/hooks/useAuth.ts
- [ ] T048 [US1] Build architect Dashboard page (project list with file/milestone counts, create project modal, archive toggle, quick stats) in frontend/src/pages/Dashboard.tsx
- [ ] T049 [US1] Build ProjectManage page (project detail/edit form, file list management, upload zone, invitation management) in frontend/src/pages/ProjectManage.tsx
- [ ] T050 [P] [US1] Build FileUploader component (drag-and-drop zone, file format validation, single PUT vs multipart detection at 100MB threshold, XHR upload progress bar) in frontend/src/components/file/FileUploader.tsx
- [ ] T051 [P] [US1] Build FileList component (grid view with thumbnail cards showing filename, file type badge, size, upload date; empty state with upload prompt) in frontend/src/components/file/FileList.tsx
- [ ] T052 [P] [US1] Build InviteForm component (email input with validation, send button with loading state, resend capability, pending/accepted status display) in frontend/src/components/project/InviteForm.tsx
- [ ] T053 [P] [US1] Build ProjectCard component (name, description, file count, milestone progress, role-appropriate actions) in frontend/src/components/project/ProjectCard.tsx
- [ ] T054 [US1] Implement useFileUpload hook (determine single vs multipart strategy, presigned URL fetch → XHR PUT with progress callback, multipart initiate → parallel part uploads → complete, abort on cancel, error handling) in frontend/src/hooks/useFileUpload.ts

**Checkpoint**: User Story 1 fully functional — architect can create projects, upload files with thumbnails, and invite clients. Client can register and access project.

---

## Phase 4: User Story 2 - Client Views Designs and Receives Real-Time Updates (Priority: P2)

**Goal**: Client can view project files with previews, and new file uploads appear automatically within 10 seconds via WebSocket (with polling fallback) without page refresh.

**Independent Test**: Open project as client → observe file list with thumbnails → architect uploads new file → new file appears on client screen automatically within 10 seconds → click file to see full preview (image/PDF/3D).

### Backend for User Story 2

- [ ] T055 [P] [US2] Implement WebSocket connection manager (in-process registry: project_id → {user_id → WebSocket}, JWT auth via query token, heartbeat ping every 30s, close codes 4001/4003/1000) in backend/src/websocket/manager.py
- [ ] T056 [P] [US2] Implement Redis PUB/SUB for cross-worker WebSocket fanout (publish on file/milestone/comment events, subscribe per worker) in backend/src/websocket/manager.py
- [ ] T057 [US2] Implement WebSocket event handlers (ws_connect: auth + project access check + subscribe, ws_disconnect: cleanup, ws_receive: ping/pong) in backend/src/websocket/handlers.py
- [ ] T058 [US2] Wire WebSocket endpoint (/ws/projects/{project_id}) into FastAPI app in backend/src/main.py
- [ ] T059 [US2] Add WebSocket broadcast to FileService (file_uploaded event with file metadata, file_deleted event) after successful upload/delete operations in backend/src/services/file.py
- [ ] T060 [US2] Implement polling fallback endpoint GET /api/projects/{project_id}/updates?since=<timestamp> returning has_updates boolean and latest timestamp from design_files + milestones in backend/src/api/routes/projects.py
- [ ] T061 [US2] Add file update notification emails (send to all project clients when new files uploaded while not connected) in backend/src/services/notification.py

### Frontend for User Story 2

- [ ] T062 [US2] Implement useWebSocket hook (connect with JWT token, exponential backoff reconnection 1s→30s max with ±25% jitter, auto-degrade to polling after 5s failure, periodic WebSocket retry every 30s, React Query cache invalidation on events) in frontend/src/hooks/useWebSocket.ts
- [ ] T063 [US2] Build client-facing ProjectView page (file list grid, milestone timeline read-only, real-time update integration via WebSocket hook, polling fallback indicator) in frontend/src/pages/ProjectView.tsx
- [ ] T064 [P] [US2] Build FileViewer component (render switch for image/PDF/3D types: <img> for images, <iframe> for PDF, <model-viewer> web component for glTF/GLB 3D models, download-only banner for unsupported formats) in frontend/src/components/file/FileViewer.tsx
- [ ] T065 [P] [US2] Build FileThumbnail component (lazy-loaded small/medium thumbnail with pending/processing/complete/failed status handling, retry on failed) in frontend/src/components/file/FileThumbnail.tsx
- [ ] T066 [US2] Create Zustand notification store (toast queue, push/dismiss actions, auto-dismiss timer, real-time event → toast mapping) in frontend/src/stores/notificationStore.ts
- [x] T066a [P] [US2] Create Notification SQLAlchemy model (user_id, type enum [file_uploaded, milestone_completed, comment_replied, invitation_received], title, body, is_read, reference_id, created_at) and add to migration in backend/src/models/notification.py
- [ ] T066b [US2] Build NotificationBell component (unread count badge, dropdown list with mark-read/dismiss, click-to-navigate to referenced project/file) and wire into Header layout in frontend/src/components/layout/Header.tsx
- [ ] T067 [US2] Build ToastContainer component (stacked toast notifications for real-time events: "New file uploaded", "File updated") in frontend/src/components/ui/ToastContainer.tsx
- [ ] T068 [US2] Update client Dashboard page to use real-time project list updates via WebSocket/React Query invalidation in frontend/src/pages/Dashboard.tsx

**Checkpoint**: User Story 2 fully functional — clients receive real-time file updates via WebSocket (or polling fallback) and can preview all file types.

---

## Phase 5: User Story 3 - Architect Organizes Progress by Milestones (Priority: P3)

**Goal**: Architect creates milestones/phases within a project, assigns design files to milestones, marks milestones complete. Client sees a visual project timeline with progress indicators.

**Independent Test**: Create project → add milestones "Concept Design", "Schematic Design" → upload files and assign to milestones → mark milestone complete → client sees timeline with completed milestone highlighted.

### Backend for User Story 3

- [ ] T069 [P] [US3] Create Milestone SQLAlchemy model with position ordering in backend/src/models/milestone.py
- [ ] T070 [P] [US3] Create Milestone Pydantic schemas (MilestoneCreate, MilestoneUpdate, MilestoneResponse with file_count) in backend/src/schemas/milestone.py
- [ ] T071 [US3] Implement MilestoneService (CRUD with position management, complete milestone with completed_at timestamp, reorder positions, list ordered by position for project) in backend/src/services/milestone.py
- [ ] T072 [US3] Implement milestone API routes (GET/POST /api/projects/{project_id}/milestones, PATCH/DELETE /api/milestones/{milestone_id}) in backend/src/api/routes/milestones.py
- [ ] T073 [US3] Add milestone_id assignment to FileService upload flow (accept optional milestone_id in presigned URL generation + upload-complete) in backend/src/services/file.py
- [ ] T074 [US3] Add milestone WebSocket events (milestone_updated, milestone_completed) to broadcast in backend/src/websocket/handlers.py
- [ ] T075 [US3] Add milestone update notification emails to NotificationService in backend/src/services/notification.py

### Frontend for User Story 3

- [ ] T076 [P] [US3] Build MilestoneTimeline component (vertical/horizontal ordered list of milestones with completion status icons, current phase highlight, file count per milestone) in frontend/src/components/milestone/MilestoneTimeline.tsx
- [ ] T077 [P] [US3] Build MilestoneCard component (milestone name, description, file count, completion toggle for architect, status badge for client) in frontend/src/components/milestone/MilestoneCard.tsx
- [ ] T078 [P] [US3] Build MilestoneForm component (create/edit modal with name, description, position fields) in frontend/src/components/milestone/MilestoneForm.tsx
- [ ] T079 [US3] Add milestone management section (create, edit, delete, reorder, mark complete) to ProjectManage page in frontend/src/pages/ProjectManage.tsx
- [ ] T080 [US3] Add milestone timeline (read-only with progress indicators) to client ProjectView page in frontend/src/pages/ProjectView.tsx
- [ ] T081 [US3] Add milestone filter dropdown and group-by-milestone view to FileList component in frontend/src/components/file/FileList.tsx
- [ ] T082 [US3] Add milestone selector to FileUploader (choose milestone when uploading) in frontend/src/components/file/FileUploader.tsx

**Checkpoint**: User Story 3 fully functional — projects organized into milestones, files grouped by phase, visual timeline for clients.

---

## Phase 6: User Story 4 - Client Provides Feedback on Designs (Priority: P4)

**Goal**: Client adds threaded comments on design files. Architect views and responds. Comments preserved across file version updates.

**Independent Test**: Client views file → adds comment → architect sees comment on file → architect replies → client sees reply. Architect replaces file → comments remain visible on updated file.

### Backend for User Story 4

- [ ] T083 [P] [US4] Create Comment SQLAlchemy model with parent_id for threading, is_resolved flag in backend/src/models/comment.py
- [ ] T084 [P] [US4] Create Comment Pydantic schemas (CommentCreate with optional parent_id, CommentUpdate, CommentResponse with nested replies array) in backend/src/schemas/comment.py
- [ ] T085 [US4] Implement CommentService (CRUD with author validation, threaded query building with recursive replies, mark resolved by architect, authorization: author or architect can edit/delete) in backend/src/services/comment.py
- [ ] T086 [US4] Implement comment API routes (GET/POST /api/files/{file_id}/comments, PATCH/DELETE /api/comments/{comment_id}) in backend/src/api/routes/comments.py
- [ ] T087 [US4] Add comment WebSocket events (comment_added) to broadcast in backend/src/websocket/handlers.py
- [ ] T088 [US4] Add comment reply notification emails to NotificationService (notify original commenter when replied to) in backend/src/services/notification.py

### Frontend for User Story 4

- [ ] T089 [P] [US4] Build CommentItem component (author avatar/name, timestamp, body text, reply button, resolve toggle for architect, edit/delete actions for author) in frontend/src/components/comment/CommentItem.tsx
- [ ] T090 [P] [US4] Build CommentForm component (text area with submit, reply mode indicator, cancel button, loading state) in frontend/src/components/comment/CommentForm.tsx
- [ ] T091 [US4] Build CommentThread component (recursive rendering of parent comments + nested replies, new comment form, resolve status filter) in frontend/src/components/comment/CommentThread.tsx
- [ ] T092 [US4] Integrate CommentThread into FileViewer side panel (shown when viewing a file, real-time comment_added event → auto-append) in frontend/src/components/file/FileViewer.tsx
- [ ] T093 [US4] Update useWebSocket hook to handle comment_added events with React Query cache invalidation for comments query in frontend/src/hooks/useWebSocket.ts
- [ ] T094 [US4] Add comment count badge and unread indicator to FileList cards in frontend/src/components/file/FileList.tsx

**Checkpoint**: User Story 4 fully functional — threaded comments on files, real-time comment updates, preserved across file versions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and ensure production readiness

- [ ] T095 [P] Add loading skeletons, empty states ("No projects yet", "Upload your first file"), and React error boundaries across all pages and components in frontend/src/
- [ ] T096 [P] Implement responsive design adjustments for tablet viewports (768px breakpoint) in all frontend layout components and pages
- [ ] T097 [P] Add security hardening: rate limiting on auth endpoints, CORS origin validation, input sanitization against XSS, SQL injection parameterization audit in backend/src/
- [ ] T098 [P] Add structured logging (request/response, errors, file operations, auth events) across backend services and routes in backend/src/
- [ ] T098a [P] Implement load testing with Locust or k6: simulate 500 concurrent users (mix of architects uploading and clients viewing), measure p95 API latency &lt;200ms, WebSocket message propagation &lt;10s, file upload throughput; document results and bottlenecks in backend/tests/load/
- [ ] T099 [P] Create backend test fixtures (async test client, test database, mocked S3, test user factory) in backend/tests/conftest.py
- [ ] T100 [P] Create frontend test setup (Vitest config with jsdom, React Testing Library setup, MSW for API mocking, render helpers) in frontend/tests/setup.ts and frontend/vitest.config.ts
- [ ] T101 Add ARQ worker command to docker-compose.yml (arq backend.src.services.thumbnail.WorkerSettings) and ensure Docker dev workflow parity
- [x] T102 Verify Constitution compliance: confirm ease of use (<5min project setup per SC-001, SC-005), reactive UI (WebSocket + progress indicators per SC-003), security (JWT + presigned URLs + RBAC per FR-015, FR-021) per .specify/memory/constitution.md
- [x] T103 Validate quickstart.md walkthrough end-to-end (docker compose up, register architect, create project, upload files, invite client, client views real-time updates) per quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — delivers MVP
- **User Story 2 (Phase 4)**: Depends on US1 (Phase 3) for project infrastructure + files — adds real-time client experience
- **User Story 3 (Phase 5)**: Depends on US1 (Phase 3) for project infrastructure — adds milestone organization
- **User Story 4 (Phase 6)**: Depends on US1 (Phase 3) for files, and US2 (Phase 4) for file viewer — adds commenting
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). No dependencies on other stories.
- **User Story 2 (P2)**: Can start after US1 (Phase 3) for file infrastructure. US1 must provide FileService, file routes, and FileViewer foundation.
- **User Story 3 (P3)**: Can start after US1 (Phase 3) for project infrastructure. US1 must provide ProjectService and project pages.
- **User Story 4 (P4)**: Can start after US1 file infrastructure + US2 file viewer are in place.

### Within Each User Story

- Models before schemas (can be parallelized within a phase)
- Models + Schemas before Services
- Services before Routes
- Routes before Frontend pages (pages consume API)
- Frontend components marked [P] can be built in parallel with backend work
- Frontend hooks bridge the gap between backend routes and frontend pages

### Parallel Opportunities

- **Phase 1**: All 6 tasks (T001-T006) can run in parallel
- **Phase 2**: T007 (migration) must complete first; T008-T019 can all run in parallel after
- **Phase 3 (US1)**: T020-T022 (models) can run in parallel; T023-T025 (schemas) can follow in parallel; T026-T031 (services) are mostly sequential but T030-T031 can be parallel with T026-T029; T032-T036 (routes) depend on services; T037-T040 (thumbnail) can run parallel with routes; T041-T054 (frontend) can start in parallel with backend once contracts are defined
- **Phase 4-6**: Backend and frontend tasks within each story can proceed in parallel
- **Phase 7**: All tasks can run in parallel

---

## Parallel Example: User Story 1

```bash
# Phase 3 models — all independent, launch together:
Task: "T020 Create User, Firm, EmailVerification, PasswordReset models in backend/src/models/user.py"
Task: "T021 Create Project, ProjectMember, Invitation models in backend/src/models/project.py"
Task: "T022 Create DesignFile, FileVersion models in backend/src/models/file.py"

# Phase 3 schemas — all independent, after models:
Task: "T023 Create auth schemas in backend/src/schemas/user.py"
Task: "T024 Create project/invitation schemas in backend/src/schemas/project.py"
Task: "T025 Create file schemas in backend/src/schemas/file.py"

# Phase 3 frontend — pages can be built in parallel with backend services:
Task: "T041 Create auth API endpoints in frontend/src/api/endpoints/auth.ts"
Task: "T044 Build Login page in frontend/src/pages/Login.tsx"
Task: "T045 Build Register page in frontend/src/pages/Register.tsx"
Task: "T046 Build InvitationAccept page in frontend/src/pages/InvitationAccept.tsx"
Task: "T050 Build FileUploader component in frontend/src/components/file/FileUploader.tsx"
Task: "T051 Build FileList component in frontend/src/components/file/FileList.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — docker-compose, project scaffolding
2. Complete Phase 2: Foundational — database, auth framework, API client, app shell
3. Complete Phase 3: User Story 1 — architect creates projects + uploads files + invites clients
4. **STOP and VALIDATE**: Register architect → create project → upload files (PNG, PDF, DWG) → verify thumbnails → invite client → register as client → verify access
5. Deploy/demo MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Architect can create projects, upload files, invite clients (MVP!)
3. Add User Story 2 → Clients get real-time updates + file previews
4. Add User Story 3 → Projects organized by milestones with visual timeline
5. Add User Story 4 → Threaded comments with real-time feedback
6. Each story adds independent value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is complete:
   - **Developer A**: User Story 1 (Phase 3) — core platform
   - **Developer B**: User Story 2 (Phase 4) — can start once US1 file infrastructure exists
   - **Developer C**: User Story 3 (Phase 5) — can start once US1 project infrastructure exists
   - **Developer D**: User Story 4 (Phase 6) — starts after US1 files + US2 file viewer

---

## Notes

- [P] tasks = different files, no dependencies on incomplete work
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable per its Independent Test criteria
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- ARQ thumbnail worker must be running for US1 file previews to work (T101)
- MinIO (S3 dev) must be available for file upload testing
- Real-time features (US2+) require WebSocket support or polling fallback verification
- Constitution compliance check (T102) covers all three principles: Ease of Use, Reactive UI, Security
"