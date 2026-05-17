# Quickstart Guide: ArchiDrive

**Date**: 2026-05-09 | **Feature**: [spec.md](./spec.md)

## Prerequisites

- Docker & Docker Compose
- Node.js 20+ and npm (for local frontend dev)
- Python 3.12+ (for local backend dev)

## Quick Start (Docker Compose)

```bash
# Clone and setup
git clone <repo-url> && cd archidrive

# Start all services
docker compose up -d

# The app is available at:
#   Frontend: http://localhost:5173
#   Backend API: http://localhost:8000
#   API Docs: http://localhost:8000/docs
#   MinIO Console: http://localhost:9001 (dev S3)
```

## Services Started

| Service | Port | Purpose |
|---------|------|---------|
| `frontend` | 5173 | React SPA (Vite dev server) |
| `backend` | 8000 | FastAPI REST + WebSocket |
| `worker` | — | ARQ task worker (thumbnails) |
| `postgres` | 5432 | PostgreSQL metadata store |
| `redis` | 6379 | ARQ task queue + WebSocket pub/sub |
| `minio` | 9000/9001 | S3-compatible dev storage |

## Manual Setup (Development)

### 1. Backend

```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your values (SECRET_KEY, S3 credentials, etc.)

# Run database migrations
alembic upgrade head

# Start dev server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start dev server
npm run dev
```

### 3. ARQ Worker (for thumbnail generation)

```bash
cd backend
source .venv/bin/activate
arq src.services.thumbnail.WorkerSettings
```

## Environment Variables

### Backend (.env)

```bash
# Required
SECRET_KEY=                  # openssl rand -hex 32
DATABASE_URL=postgresql+asyncpg://archidrive:archidrive@localhost:5432/archidrive
REDIS_URL=redis://localhost:6379

# S3 Storage (MinIO for dev)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=archidrive
S3_REGION=us-east-1

# Email (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxx
EMAIL_FROM=Archidrive <__VG_EMAIL_48aa05360795__>

# App
FRONTEND_URL=http://localhost:5173
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Frontend (.env)

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=localhost:8000
```

## First Run

1. Open http://localhost:5173
2. Register as an architect
3. Create a project
4. Upload design files (drag & drop supported)
5. Invite a client via email
6. Open client invitation link in an incognito window
7. Client registers and sees the project with real-time file updates

## Running Tests

```bash
# Backend tests
cd backend && pytest -v

# Frontend tests
cd frontend && npm test
```

## Architecture Overview

```
Browser (React SPA)
    │
    ├── HTTP/REST ──── FastAPI (port 8000)
    │                      │
    ├── WebSocket ────     ├── SQLAlchemy (async) ── PostgreSQL
    │                      │
    │                      ├── boto3 ─────────────── S3 / MinIO
    │                      │
    │                      └── ARQ ──────────────── Redis
    │                           │
    └── Direct PUT ───────── S3 / MinIO (presigned URLs)
```

## Key URLs

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Frontend app |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/redoc | ReDoc API docs |
| http://localhost:9001 | MinIO Console (user: minioadmin / minioadmin) |

## Project Structure

```
archidrive/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Config, security, database
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic
│   │   ├── websocket/    # WebSocket manager + handlers
│   │   └── main.py       # App entry point
│   ├── migrations/       # Alembic migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/          # Axios client + endpoint functions
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks
│   │   ├── pages/        # Route pages
│   │   ├── stores/       # Zustand stores
│   │   └── types/        # TypeScript types
│   ├── tests/
│   └── package.json
├── docker-compose.yml
└── specs/
    └── 001-architect-client-portal/
        ├── spec.md
        ├── plan.md
        ├── research.md
        ├── data-model.md
        ├── quickstart.md
        └── contracts/
            └── api.yaml
```
