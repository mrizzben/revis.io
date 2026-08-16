# Quickstart: Internal Team Collaboration

**Date**: 2026-08-08 | **Feature**: [spec.md](./spec.md)

## Prerequisites

- Running revis.io stack (see root `docker-compose.yml` — backend on `:8000`, frontend on `:5173`, PostgreSQL, RustFS).
- Python 3.12 (backend), Node.js 20+ (frontend).

## Setup & Run

```bash
# 1. Start the full stack
docker compose up -d

# 2. Apply the new migration (new tables + role/notification enum values)
docker compose exec backend alembic upgrade head
```

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- API Docs: <http://localhost:8000/docs>

## Try It (dev flow)

1. Log in as an **architect** and open a project.
2. In the project, open the **Internal** panel → **Add collaborator** → enter a teammate's email.
3. Share that teammate's account link; when they log in, they see the project's internal panel (notes + to-dos) but no client-only surface changes.
4. Write an **internal note** with an `@mention` — the named collaborator receives an in-app notification.
5. Create a **to-do**, assign it to the collaborator; they mark it complete.
6. Verify as a **client** on the same project that the internal panel, notes, mentions, and to-dos are **never visible**.

## Verify

- Backend tests: `docker compose exec backend pytest tests/test_collaborators.py tests/test_internal_notes.py tests/test_todos.py tests/test_internal_visibility.py -q`
- Frontend: `cd frontend && npm test`
- Role check: a `client` role user calling any internal endpoint receives `404` (not `403`), confirming no internal-content disclosure.
