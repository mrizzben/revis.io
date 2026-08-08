# Research: Scope Gap Analysis — Architect-Client Design Portal

**Date**: 2026
**Context**: App targets architects collaborating *internally* **and** with *clients*, updating progress in real time. This doc reviews the two existing feature specs and recommends what to add next.

---

## Current Scope (what's already specced)

### `specs/001-architect-client-portal`

- Project creation, file upload (1 GB, image/PDF/CAD/3D formats), previews/thumbnails
- Real-time updates to clients on upload/change
- Email notifications (when client not viewing)
- Milestones / phases with completion status + timeline
- Client feedback / comments on design files
- Invitations (unique secure links, resend/expiry) + access control
- Firm / role ownership (firm-owned projects, reassignment)
- Unified dashboard for each user

### `specs/003-kanban-board-view`

- Milestones rendered as columns, files as cards
- Drag-and-drop reassignment (architect only)
- Timeline ↔ board toggle
- Read-only board for clients

---

## The Core Gap

The app's stated goal is *"architects collaborate internally and to their clients."*
The specs fully cover the **architect → client** direction, but **internal team
collaboration is nearly absent** — only firm ownership + reassignment (an 001
edge case) exists. This is the biggest mismatch with the product's own positioning.

---

## Candidate Additions (roughly by priority)

| # | Candidate | Why it fits | Value |
| --- | ----------- | ------------- | ------- |
| 1 | **Internal team collaboration** — add collaborators to a project, internal-only notes/@mentions hidden from clients, assignable to-dos | Closes the "collaborate internally" half of the goal; biggest gap | Highest |
| 2 | **File versioning + change log** — upload new revisions, keep history, show visible "changed" state to clients | Already assumed by 3 edge cases in 001/003 ("preserve comments across versions", "update appears without re-navigate") but never specced | High |
| 3 | **Client approvals / sign-offs** — mark deliverable as approved / revisions requested | Tangible go/no-go signal; natural extension of milestones + feedback | High |
| 4 | **Activity feed / project timeline** — chronological record of uploads, milestone changes, comments | Gives the "progress tracking" half of the goal a home; cheap on top of existing events | Medium |
| 5 | **In-app notifications** — notification center/bell (currently email-only) | Explicit edge case in 001, currently unimplemented | Medium |

### Deferred (scope-creep risk)

- Side-by-side version comparison
- Public read-only share links
- Granular per-milestone client visibility
- PDF progress-report export
- On-image pin annotations

---

## Recommendation

Specs are single-feature. Pick one at a time:

1. **Best next pick: #1 (internal team collaboration)** — the one place the
   current scope genuinely misses the "collaborate internally" promise.
2. **Most de-risking follow-up: #2 (file versioning)** — three existing edge
   cases already assume version history exists.
