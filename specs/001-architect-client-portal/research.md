# Research Report: Architect-Client Design Portal

**Date**: 2026-05-09 | **Feature**: [spec.md](./spec.md)

## 1. Authentication & Authorization

### Decision: PyJWT + pwdlib (Argon2), httpOnly refresh token cookies, invitation-based onboarding

**Rationale**:
- FastAPI's latest documentation recommends PyJWT over python-jose and pwdlib with Argon2 over passlib (which breaks on Python 3.13+)
- Refresh tokens stored in httpOnly, Secure, SameSite=Strict cookies prevent XSS exfiltration
- Access tokens (15min lifespan) stored in Zustand store for API requests; short blast radius if leaked
- Invitation flow: token in email → client registers → token validated → auto-granted project access

**Alternatives considered**: python-jose (wrapper around PyJWT — unnecessary layer), passlib (unmaintained, breaks on Python 3.13+), localStorage for refresh tokens (XSS-vulnerable)

### Token Structure
- **Access Token**: `{sub: user_id, role, firm_id, type: "access", exp, iat}` — 15 min
- **Refresh Token**: `{sub: user_id, type: "refresh", exp, iat}` — 7 days

### Frontend Auth Flow
- Zustand store with `persist` middleware for access token + user profile
- Axios request interceptor attaches Bearer token; response interceptor auto-refreshes on 401 with request queuing
- `useAuth` hook handles login/logout/session restoration via `/api/auth/refresh`

### Email Service: Resend
- Modern Python SDK with async support, 100 free emails/day, official FastAPI example
- React Email integration for beautiful transactional templates
- SES as future fallback at scale (>100k emails/month)

---

## 2. File Upload Strategy

### Decision: Direct-to-S3 Presigned URLs with XHR Progress Tracking

**Rationale**:
- Server-proxied uploads double bandwidth and create bottlenecks for 1GB files
- Presigned URLs keep the backend lightweight (URL generation only), scale with S3 infrastructure
- XHR (not fetch) required for upload progress — `fetch` API does not support `upload.progress` events
- Once upload begins, it completes even if URL expires mid-transfer

### Multipart Strategy for Files >100MB
- Single PUT (presigned URL) for ≤100MB files
- S3 Multipart Upload with presigned part URLs for >100MB
- **Part size**: 25 MiB → ~40 parts for 1GB file
- **Concurrency**: 5 parallel part uploads
- **Lifecycle rule**: Auto-abort incomplete multipart uploads after 7 days

### Security
- Content-Type baked into presigned URL — S3 rejects mismatches
- Server-side validation before URL generation: file extension, content type, file size, project access
- SSE-S3 encryption enforced on all uploads
- S3 Block Public Access enabled; all downloads via authenticated presigned URLs

### Post-Upload Processing: Hybrid Trigger
- **Primary**: S3 Event Notification → Lambda → thumbnail generation
- **Fallback**: Frontend calls `POST /api/files/{fileId}/upload-complete` → ARQ background task
- The fallback ensures dev/prod parity with S3-compatible storage (MinIO)

---

## 3. Thumbnail & Preview Generation

### Format Support Matrix

| Format | Library | License | Thumbnail | 3D Preview |
|--------|---------|---------|-----------|------------|
| PNG, JPEG, WebP | Pillow | MIT-CMU | ✅ | ✅ (native img) |
| PDF | PyMuPDF | AGPL | ✅ | ✅ (iframe) |
| DXF | ezdxf + matplotlib | MIT | ✅ | ❌ |
| DWG | ODA FC → DXF → ezdxf | Free CLI / MIT | ✅ | ❌ |
| IFC | IfcOpenShell + trimesh | LGPL / MIT | ✅ | ✅ (glTF via model-viewer) |
| OBJ, STL | trimesh + pyrender | MIT | ✅ | ✅ (glTF via model-viewer) |
| SKP, RVT | — | — | ❌ | ❌ |

**SKP/RVT**: Download-only with file-type icon. Proprietary formats with no viable open-source Python library.

### Background Processing: ARQ
- Redis-backed async task queue (700 lines vs Celery's 50k+)
- Same asyncio event loop as FastAPI — no impedance mismatch
- Job deduplication via `_job_id=f"thumbnail:{file_id}"`
- Timeout: 120s (IFC/DWG), 30s (others); 3 retries with exponential backoff

### Thumbnail Specifications
- **Format**: WebP at quality 85 (30% smaller than JPEG)
- **Sizes**: small (200×200) for grids/lists, medium (600×600) for detail view
- **Storage**: `thumbnails/{file_id}/{small|medium}.webp`
- **Serving**: Authenticated backend endpoint → presigned S3 URL (5-min expiry)

### Browser 3D Preview: `<model-viewer>`
- Google web component, ~200KB gzipped, zero configuration
- Supports glTF/GLB (generated server-side from IFC/OBJ/STL via IfcConvert/trimesh)
- Auto-rotate, orbit/pan/zoom controls, AR mode

---

## 4. Real-Time Updates

### Decision: WebSocket (primary) with Long Polling (fallback)

**Rationale**:
- SSE's 6-connection browser limit (HTTP/1.1) is a dealbreaker for multi-project clients
- WebSocket provides full-duplex communication for future commenting/feedback features
- Sub-second latency vs polling's 5-30s interval
- Spec requires fallback to polling (Assumptions section)

### WebSocket Architecture

**Backend — ProjectRoomManager**:
- In-process connection registry: `{project_id: {user_id: WebSocket}}`
- Redis PUB/SUB for cross-worker fanout (multi-uvicorn deployments)
- Authentication: JWT as query parameter (`?token=<jwt>`)
- Heartbeat: server ping every 30 seconds
- Close codes: 4001 (auth failed), 4003 (access denied), 1000 (normal)

**Frontend — `useRealtimeTransport` hook**:
- WebSocket connection with exponential backoff reconnection (1s → 30s max, ±25% jitter)
- Auto-degradation to polling if WebSocket fails within 5 seconds
- Periodic WebSocket retry every 30 seconds while polling
- React Query invalidation on events (NOT state duplication)

**Event Flow**:
```
Architect uploads file → S3 → API callback → ARQ generates thumbnail
    → DB updated → manager.broadcast_to_project("file_uploaded")
    → All connected clients receive event → React Query invalidates queries
    → UI refreshes with new file list + thumbnail
```

**Polling fallback endpoint**: `GET /projects/{project_id}/updates?since=<timestamp>` — lightweight, checks MAX(updated_at) from files/milestones tables.

### Nginx Configuration
- `proxy_read_timeout 3600s` for WebSocket
- `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"`

---

## 5. Technology Stack Summary

| Layer | Choice | Key Dependencies |
|-------|--------|-----------------|
| Backend framework | Python 3.12 + FastAPI | uvicorn, websockets |
| Database | PostgreSQL 16 | SQLAlchemy 2.x (async), Alembic |
| ORM | SQLAlchemy 2.x async | asyncpg |
| File storage | S3-compatible (AWS S3 / MinIO) | boto3 |
| Auth | PyJWT + pwdlib (Argon2) | cryptography, pwdlib |
| Background tasks | ARQ | redis[hiredis] |
| Thumbnails | Pillow, PyMuPDF, ezdxf, trimesh | matplotlib, pyrender, ifcopenshell |
| Email | Resend | resend |
| Frontend | TypeScript 5 + React 18 | Vite, React Router 6, Tailwind CSS |
| State management | Zustand + TanStack Query | zustand, @tanstack/react-query |
| 3D viewing | model-viewer web component | @google/model-viewer |
| Testing (BE) | pytest + httpx | pytest-asyncio, pytest-cov |
| Testing (FE) | Vitest + React Testing Library | @testing-library/react |
| Containerization | Docker + Docker Compose | postgres:16, minio, redis:7 |
