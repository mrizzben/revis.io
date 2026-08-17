# revis.io

**Git for architects, designers, and graphic design professionals** — a version control and collaboration platform purpose-built for the architecture and design workflow. Just as Git enables developers to track code changes, collaborate, and manage versions, Revis.io delivers the same core capabilities tailored for design files including CAD drawings, PDFs, images, and 3D models.

`revis.io` is a project focused on delivering a seamless and secure experience. Our core development is guided by three primary principles:

- **Ease of Use**: Prioritizing a frictionless and intuitive user experience.
- **Reactive UI**: Leveraging reactive patterns to ensure a responsive and dynamic interface.
- **Security**: Integrating robust security best practices into every layer of the application.

## Project Summary

A real-time web application where architects present design files to clients, track milestone progress, and receive client feedback. Architects create projects, upload design files (CAD, PDF, images, 3D models) to S3, and invite clients via email — or share a secure link for zero-signup access. Clients view designs in near real-time as the architect updates files, with milestone tracking and contextual commenting. Architects and their teams collaborate on revisions internally before issuing them to clients, with full version and audit history. Firm accounts provide organizational ownership and project reassignment.

## Key Features

- **Authentication**: Email/password sign-up with verification and forgot-password/reset flow, or **Google OAuth** sign-in/sign-up (optional; enable with `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`)
- **Access models**: App **admin role** with platform-wide visibility, **firm accounts** with ownership and project reassignment, and **client secure links** — token-based access so clients can view projects without signing up
- **Team collaboration**: Project collaborators, internal notes with `@mentions` and threaded replies, and assignable/status-tracked to-dos — all internal content is hidden from clients
- **Revision management**: Versioned design files with an explicit workflow — internal review → issue to client → supersede → archive, plus restore, named checkpoints, revision-scoped comments, **design options** for parallel exploration, and an append-only **activity feed**
- **Real-time updates**: WebSocket push for file changes, comments, notifications, and team activity
- **Large-file support**: Presigned multipart uploads up to 1GB, auto-generated thumbnails/previews, inline viewing of PDFs and images

## Technical Stack

- **Languages**: Backend: Python 3.12; Frontend: TypeScript 5 + React 18
- **Primary Dependencies**: FastAPI (async HTTP + WebSockets), SQLAlchemy 2.x (async ORM), boto3 (S3), Google OAuth, Resend (email), ARQ (task queue), React Router 6, Zustand (state management), TanStack Query (server state), Tailwind CSS
- **Storage**: PostgreSQL 16 (metadata, users, projects, milestones, comments) + S3-compatible object storage (design files and thumbnails)
- **Testing**: Backend: pytest + httpx (async); Frontend: Vitest + React Testing Library
- **Performance Goals**: 500 concurrent users, real-time file update propagation <10 seconds, API p95 latency <200ms
- **Scale/Scope**: ~100 architects, ~400 clients, ~1000 projects, ~10k design files initially
- **Target Platform**: Modern web browsers (Chrome, Firefox, Safari, Edge latest 2 versions); Linux server (Docker containers)
- **Constraints**: File uploads up to 1GB via presigned S3 URLs, thumbnail generation <30s, initial deployment ≤100GB stored files

## Getting Started

### Quick Start (Docker Compose - Recommended)

```bash
# Clone and setup
git clone <repo-url> && cd revis.io

# Start all services
docker compose up -d
```

The app will be available at:

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>
- **RustFS Console**: <http://localhost:9001> (dev S3)

### Services Started

| Service | Port | Purpose |
| --------- | ------ | --------- |
| `frontend` | 5173 | React SPA (Vite dev server) |
| `backend` | 8000 | FastAPI REST + WebSocket |
| `worker` | — | ARQ task worker (thumbnails) |
| `postgres` | 5432 | PostgreSQL metadata store |
| `redis` | 6379 | ARQ task queue + WebSocket pub/sub |
| `rustfs` | 9000/9001 | S3-compatible dev storage |

### Manual Setup (Development)

**Backend:**

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your values
# Optional: set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET to enable Google sign-in
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, start the background worker (thumbnails):

```bash
cd backend && source .venv/bin/activate
arq src.services.thumbnail.WorkerSettings
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend && pytest -v

# Frontend tests
cd frontend && npm test
```

## Project Structure

- `backend/`: Python FastAPI service with async ORM, S3 integration, WebSocket support
- `frontend/`: TypeScript React SPA with reactive state management, real-time updates
- `specs/`: Feature planning, research, and specification documents
- `docker-compose.yml`: Local development environment with PostgreSQL, RustFS, and app services

For more information on the project's governance and core principles, please refer to the [Constitution](.specify/memory/constitution.md).
