# ArchiDrive Targets

## Product Direction

ArchiDrive is **Git for architects**: a system for tracking design artifacts, revisions, issued packages, review decisions, and project traceability.

It should borrow Git's useful ideas—history, checkpoints, comparison, review, and restore—without copying developer workflows that do not fit architecture.

## Target Model

```text
Project
└── Design item / document
    ├── Revision 1
    ├── Revision 2
    └── Revision 3

Revision
├── author
├── timestamp
├── message
├── visibility
├── review status
└── issue/checkpoint status
```

A design item is the stable identity. An uploaded object is a revision of that item, not a new unrelated file.

## Priority Targets

**Implementation status: all targets below are implemented as of 2026-08-30** and merged to `development` (`9337a7b`, pushed). T1–T3, T5–T7 landed in the revision-management round (`8de258f`); T4 Phase 2 and T8 automation landed in the three-parallel-lane round (`9337a7b`, see `REVIEW.md`). Backend 116 tests green, frontend `tsc` clean. Remaining work is verification/deployment hardening, not features — live ARQ worker, live clamd container, retention at scale — listed under [Delivered vs still-to-prove](#delivered-vs-still-to-prove).

### T1 — File revisions

**Status: ✅ implemented** — separate upload-complete records a version on the stable file identity; version list/download/restore routes; revision messages; revision-scoped comments kept.

**Goal:** Preserve the identity and complete history of a design file while allowing new uploads.

Required behavior:

- Upload a new revision to an existing design item.
- Keep the existing design item URL and identity stable.
- Record revision number, author, timestamp, size, storage key, and content hash.
- Show the current revision clearly.
- List and download prior revisions.
- Restore a prior revision as the current revision without deleting history.
- Add a short revision message.
- Preserve comments and clearly indicate whether they apply to one revision or all revisions.
- Broadcast revision changes to connected project members.

Existing starting points:

- `backend/src/models/file.py` already contains `FileVersion`.
- `backend/src/services/file.py` already contains `create_file_version()`.
- Replace hardcoded `version_number: 1` responses.

Done when:

- A second upload is stored as revision 2 of the same design item.
- Revision history is visible in the API and frontend.
- Restoring revision 1 makes it current while retaining revisions 1 and 2.
- Existing comments are not lost.

### T2 — Named checkpoints and issues

**Status: ✅ implemented** — name/description/revision_message; issue/supersede/archive endpoints; explicit issue action (never a side effect of upload); client sees only issued/superseded.

**Goal:** Give revisions architectural meaning instead of exposing only raw upload history.

Required behavior:

- Name a revision or checkpoint, for example `Planning submission`.
- Record an optional description or issue note.
- Mark a revision as internal draft or issued to client.
- Record who issued it and when.
- Mark superseded revisions without deleting them.
- Associate checkpoints with project milestones.
- Allow clients to see only intentionally issued revisions.

Example states:

```text
draft → internal review → issued to client → superseded → archived
```

Done when:

- An architect can issue a specific revision to a client.
- A client cannot see internal drafts.
- The project history explains which revision was officially issued and why.

### T3 — Review workflow

**Status: ✅ implemented** — request/assign/transition (`draft → in_review → changes_requested/approved`), decision audit, client-scoped reviews, internal-team notifications.

**Goal:** Turn comments into an explicit design review process.

Required behavior:

- Request review from a collaborator or client.
- Assign a reviewer.
- Track review status:
  - draft
  - in review
  - changes requested
  - approved
- Attach comments to a specific revision when appropriate.
- Resolve and reopen review comments.
- Record approval/rejection author and timestamp.
- Notify the relevant internal team members.
- Keep an immutable review history.

Done when:

- A reviewer can approve a specific revision.
- A reviewer can request changes.
- The team can distinguish an approved revision from an obsolete comment thread.
- Clients only participate in reviews explicitly opened to them.

### T4 — Comparison

**Status: ✅ implemented (Phase 1 + Phase 2)** — metadata + side-by-side/overlay (Phase 1) and server-side PDF change highlighting, page alignment, per-page diff metrics/badges (Phase 2, `diffing.py` + `CompareModal` DiffView). CAD/BIM/3D diffing remains deferred (below).

**Goal:** Make revision changes understandable without requiring external software.

Phase 1:

- PDF page comparison.
- Image overlay with opacity control.
- Side-by-side comparison.
- Revision metadata and change message beside the comparison.

Phase 2:

- PDF change highlighting.
- Drawing sheet/page alignment.
- Thumbnail-level visual difference indicator.

Deferred:

- CAD geometric diffing.
- BIM model comparison.
- Full 3D scene diffing.

Done when:

- A user can select two revisions and compare them.
- PDF and image revisions support a useful side-by-side or overlay view.
- Unsupported formats explain that comparison is unavailable rather than failing silently.

### T5 — Design options

**Status: ✅ implemented** — create/fork/promote/archive; archived options hidden from client view; history preserved.

**Goal:** Support parallel design exploration without implementing arbitrary Git branches.

Use the architectural term **design option**, not branch.

Required behavior:

- Create an option such as `Option A` or `Courtyard scheme`.
- Copy or fork a design item into an option.
- Keep option revisions separate.
- Mark one option as current or preferred.
- Archive rejected options.
- Prevent archived options from appearing in the normal client view.

Deferred:

- Arbitrary branching from any project state.
- Three-way merge.
- Automatic conflict resolution.

Done when:

- Two alternatives can be developed independently.
- The architect can promote one option to the current client-facing path.
- No revision history is destroyed when an option is rejected.

### T6 — Activity and audit history

**Status: ✅ implemented** — append-only `ActivityEvent`, visibility-scoped timelines, event-type filter, callers wired into upload/issue/review paths.

**Goal:** Provide a durable explanation of what happened in a project.

Record events for:

- File uploaded.
- Revision created.
- Revision restored.
- Revision issued or superseded.
- Review requested.
- Review approved or rejected.
- Changes requested.
- Comment created, resolved, or reopened.
- Milestone changed.
- Client invited.
- Collaborator added or removed.
- Permission or visibility changed.
- Project archived.

Recommended shape:

```text
activity_events
├── project_id
├── actor_id
├── event_type
├── entity_type
├── entity_id
├── payload
└── created_at
```

Requirements:

- Append-only from the application perspective.
- Never expose internal events to clients.
- Support project timeline filtering by event type.
- Keep enough metadata to explain who changed what and when.

Done when:

- A project has a trustworthy chronological history.
- Internal and client-facing timelines enforce the same visibility rules as the underlying entities.

### T7 — Revision-level visibility and permissions

**Status: ✅ implemented** — `CLIENT_VISIBLE_VISIBILITIES` enforced across file list, download, thumbnails, compare, reviews, activity, WS; issue is explicit.

**Goal:** Ensure uploaded work is not automatically client-visible.

Minimum visibility levels:

- `internal`
- `review`
- `client_issued`
- `superseded`
- `archived`

Rules:

- Internal drafts are visible only to the owner and collaborators.
- Client-issued revisions are visible to authorized clients.
- Superseded revisions remain available to internal users.
- Archived revisions are hidden from normal views but retained for audit/history.
- Download, preview, thumbnails, WebSocket events, search, and project payloads must all apply the same visibility rules.

Done when:

- A client cannot infer or retrieve an internal revision through any endpoint or real-time channel.
- Issuing a revision is an explicit action, not a side effect of upload.

### T8 — File identity, integrity, and storage lifecycle

**Status: ✅ implemented** — content hash, dedupe, clamd INSTREAM scan (issue blocked while infected), abandoned-multipart cleanup, soft-delete → hard purge, storage usage/orphans, and a scheduled auto-maintenance loop (`9337a7b`).

**Goal:** Make large architectural files safe and predictable to manage.

Required behavior:

- Store a content hash for every completed revision.
- Detect duplicate uploads where practical.
- Keep revision storage keys immutable.
- Recover or clearly fail interrupted uploads.
- Clean up abandoned multipart uploads.
- Track storage usage by project and firm.
- Validate file content and MIME type at the trust boundary.
- Scan uploaded files for malware before making them available.
- Define retention and deletion behavior.

Done when:

- A revision cannot silently change underneath its history record.
- Abandoned uploads do not grow storage forever.
- The system can report storage usage and identify orphaned objects.

## Suggested Delivery Order

**Completed** — the original order (T1 → T2 → T3 → T6 → T7 → T4 → T8 → T5) shipped in two rounds; all eight are in `development`.

## Delivered vs still-to-prove

Implemented code behind every target, but three operational paths are verified at unit level only and need a live environment to prove:

- ARQ diff job (enqueue → poll → ready) against a running Redis + compose worker.
- clamd malware scan against a real clamav container (`docker compose up clamav`, healthcheck + an infected-fixture scan).
- Retention/abandoned-upload maintenance at scale (scheduler runs every 6h; watch `aborted_multipart_uploads`/`purged_soft_deleted_files` in logs).

Adding a CI job that runs the compose stack (postgres + redis + rustfs + clamav + worker) and exercises these would close the gap.

## Explicitly Not Targets Yet

Do not build these until user evidence justifies them:

- Full CAD or BIM geometric diffing.
- Arbitrary Git-style branching and merging.
- Automatic three-way merge.
- Project-wide snapshots of every file.
- Public read-only share links.
- PDF progress-report export.
- Per-milestone client visibility.
- On-image pin annotations.

## Product Test

ArchiDrive is moving in the right direction if an architect can answer these questions without opening another tool:

1. What is the current revision?
2. What changed since the last issue?
3. Who reviewed it?
4. What remains unresolved?
5. What did the client actually receive?
6. Can I restore the previous approved revision?
7. Who changed this, and when?

If a feature does not improve one of those answers, it is probably not part of the Git-for-architects core.
