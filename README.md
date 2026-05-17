# archidrive

**Git for architects, designers, and graphic design professionals** — a version control and collaboration platform purpose-built for the architecture and design workflow. Just as Git enables developers to track code changes, collaborate, and manage versions, ArchiDrive delivers the same core capabilities tailored for design files including CAD drawings, PDFs, images, and 3D models.

`archidrive` is a project focused on delivering a seamless and secure experience. Our core development is guided by three primary principles:

- **Ease of Use**: Prioritizing a frictionless and intuitive user experience.
- **Reactive UI**: Leveraging reactive patterns to ensure a responsive and dynamic interface.
- **Security**: Integrating robust security best practices into every layer of the application.

## Project Summary

A real-time web application where architects present design files to clients, track milestone progress, and receive client feedback. Architects create projects, upload design files (CAD, PDF, images, 3D models) to S3, and invite clients via email. Clients view designs in near real-time as the architect updates files, with milestone tracking and contextual commenting. Firm accounts provide organizational ownership and project reassignment.

## Technical Stack

- **Languages**: Backend: Python 3.12; Frontend: TypeScript 5 + React 18
- **Primary Dependencies**: FastAPI (async HTTP + WebSockets), SQLAlchemy 2.x (async ORM), boto3 (S3), React Router 6, Zustand (state management), TanStack Query (server state), Tailwind CSS
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
git clone <repo-url> && cd archidrive

# Start all services
docker compose up -d
```

The app will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (dev S3)

### Services Started

| Service | Port | Purpose |
|---------|------|---------|
| `frontend` | 5173 | React SPA (Vite dev server) |
| `backend` | 8000 | FastAPI REST + WebSocket |
| `worker` | — | ARQ task worker (thumbnails) |
| `postgres` | 5432 | PostgreSQL metadata store |
| `redis` | 6379 | ARQ task queue + WebSocket pub/sub |
| `minio` | 9000/9001 | S3-compatible dev storage |

### Manual Setup (Development)

**Backend:**
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your values
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
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
- `docker-compose.yml`: Local development environment with PostgreSQL, MinIO, and app services

For more information on the project's governance and core principles, please refer to the [Constitution](.specify/memory/constitution.md).
