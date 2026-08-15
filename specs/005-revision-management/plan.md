# Implementation Plan: Revision Management, Reviews, Activity, Visibility, Options

**Date**: 2026-08-15 | **Input**: [TARGETS.md](../../TARGETS.md) (T1–T8)

## Summary

Implements the "Git for architects" core loop — **upload revision → review → issue to
client → supersede or restore** — across eight targets: file revisions (T1), named
checkpoints and issuance (T2), the review workflow (T3), activity/audit history (T6),
revision-level visibility (T7), PDF/image comparison (T4), file integrity and storage
lifecycle (T8), and design options (T5).

## Data model

| Entity | Change |
| ------ | ------ |
| `design_files` | + `design_option_id`, `parent_file_id`, `current_version_id` |
| `file_versions` | + `revision_message`, `name` (checkpoint), `description`, `content_hash`, `visibility` (internal/review/client_issued/superseded/archived), `issued_by_id/issued_at`, `superseded_by_id/superseded_at`, `milestone_id`, `scan_status`, `mime_valid`, `restored_from_superseded` |
| `design_options` | NEW — parallel design exploration (T5) |
| `activity_events` | NEW — append-only audit history (T6) |
| `reviews` | NEW — explicit review workflow (T3) |
| `comments` | + `version_id` (revision-scoped comments, T1), `resolved_at/resolved_by_id` (T3 audit) |
| `notifications` | + `review_requested`, `review_updated`, `revision_issued` types |

Migration: `backend/migrations/versions/003_revision_management.py`.

## Revision lifecycle (T1/T2/T7)

```
upload (internal draft)
  → send to internal review (review)            [POST /files/{id}/versions/{n}/review]
  → issue to client (client_issued)             [POST .../issue]   — explicit, never a side effect of upload
  → superseded (superseded)                     [POST .../supersede]
  → archived (archived)                         [POST .../archive]
restore (restore makes a revision current)      [POST .../restore]
```

- **Issuing is explicit**: a fresh upload is always `internal`; issuing records
  `issued_by/issued_at` and supersedes any previously client-issued revision.
- **Restore** re-promotes a superseded revision to `client_issued` and updates the
  item's `current_version_id` without deleting history.
- **Clients see only issued history** (`client_issued` + `superseded`), with the latest
  issued revision presented as current. Every client-facing surface enforces this:
  file list, project payload, download, thumbnail, preview, version detail/download,
  compare, reviews, WebSocket events, and activity timeline.

## Key endpoints

- `POST /files/upload-url` and `/files/multipart/initiate` accept `file_id` to upload
  a new revision of an existing item (stable identity) plus `revision_message`/`name`/
  `description`/`design_option_id`.
- `POST /files/{id}/upload-complete` records the revision and runs trust-boundary
  checks: content hash (SHA-256, streamed from S3), magic-byte MIME validation,
  clamd malware scan, and content dedupe (identical hash → reuse existing immutable key).
- `GET /files/{id}/versions`, `GET/PATCH /files/{id}/versions/{n}`,
  `POST .../restore|issue|supersede|archive|review|scan`, `GET .../versions/{n}/download`.
- `POST /files/{id}/compare` — comparison metadata + presigned view URLs (T4).
- `POST /files/{id}/reviews`, `GET /files/{id}/reviews`, `POST /reviews/{id}/transition`
  (`start|approve|request_changes`) (T3).
- `GET /projects/{id}/activity?event_type=` (T6).
- `GET /storage/usage`, `GET /storage/orphans`, `POST /storage/maintenance` (T8).
- `GET/POST /projects/{id}/options`, `PATCH /options/{id}`, `POST /options/{id}/fork`,
  `GET /options/{id}/files` (T5).

## Malware scanning (T8)

- `CLAMD_HOST`/`CLAMD_PORT` settings; clamd `INSTREAM` protocol over a stdlib socket —
  no new dependencies.
- Objects ≤ `MALWARE_SCAN_MAX_SIZE` (default 500 MB) are scanned at upload-complete.
- Verdicts: `pending` → `clean` / `infected` / `error` / `skipped` (no clamd configured,
  or object too large).
- **Issue is blocked for infected revisions** (409). `POST .../scan` re-runs a scan.

## Storage lifecycle & retention (T8)

- **Retention / deletion behavior**:
  - Uploads are immutable: every revision's `s3_key` is content-addressed and never
    rewritten. Deduplicated revisions share a key; an object is deleted only when no
    revision references it.
  - Deleted items are **soft-deleted** (architect `DELETE /files/{id}`) so history and
    references survive accidental deletion.
  - Soft-deleted items older than `SOFT_DELETE_RETENTION_SECONDS` (default 30 days) are
    hard-purged by `POST /storage/maintenance`, which first deletes each referenced S3
    object that no other revision uses.
  - Abandoned multipart uploads older than `MULTIPART_ABANDON_AFTER_SECONDS`
    (default 7 days) are aborted by the same maintenance endpoint — abandoned uploads
    cannot grow storage forever.
  - Storage usage is reported per project and per firm (`GET /storage/usage`);
    orphaned objects (keys under `uploads/` referenced by no revision) are listed by
    `GET /storage/orphans`.
- **Interrupted uploads fail clearly**: `upload-complete` returns 409 with a
  "re-upload" message when the S3 object is missing, and records no version.

## Activity / audit history (T6)

- `activity_events` is append-only from the application perspective: no update/delete
  path exists.
- Events recorded: `revision_created`, `revision_restored`, `revision_issued`,
  `revision_superseded`, `revision_archived`, `revision_updated`, `comment_created`,
  `comment_resolved`, `comment_reopened`, `review_requested`, `review_approved`,
  `review_changes_requested`, `review_in_review`, `milestone_changed`, `file_deleted`,
  `item_forked`, `option_created`, `option_updated`.
- Each event stores `project_id`, `actor_id`, `event_type`, `entity_type`,
  `entity_id`, JSON `payload`, and `created_at` — enough to explain who changed what
  and when.
- **Visibility**: events carry an `internal`/`client` flag set at record time to match
  the underlying entity's visibility; client timelines only ever see `client` events.
- Timeline filtering by `event_type` supported.

## Review workflow (T3)

- Request review (assign a reviewer — owner/collaborator), optionally open it to the
  client (`is_client_review`).
- Status: `draft → in_review → changes_requested/approved`; approvals and change
  requests record `decided_by/decided_at` and a decision comment.
- Immutable history via `activity_events`; internal-team notifications via the
  existing Notification model.
- Clients see only reviews explicitly opened to them (and can transition only those).

## Design options (T5)

- Create options (`Option A`, `Courtyard scheme`), fork design items into an option
  (copying the full revision history with a `parent_file_id` lineage link), promote one
  option as current, archive rejected options.
- Archived options are excluded from the normal client view; no history is destroyed.
- Option revisions are fully separate from the main line.

## Comparison (T4)

- `POST /files/{id}/compare` supports PDFs and images (png/jpg/jpeg/webp) with
  side-by-side and image-overlay (opacity slider) views in the frontend, plus revision
  metadata and change messages beside the comparison.
- Unsupported formats return an explicit explanation with download links instead of
  failing silently.

## Frontend

- `components/revision/` — `RevisionPanel` (history + restore/issue/supersede/archive/
  rename/compare/download), `CompareModal`, `ReviewPanel`.
- `components/activity/ActivityTimeline.tsx`, `components/options/OptionsPanel.tsx`.
- `FileViewer` shows the revision panel, review panel, revision-scoped comments;
  `FileUploader` supports uploading a new revision with a change message.
- `useWebSocket` invalidates queries on `revision_*`/`review_*` events.

## Verification

- Backend: `pytest` — 63 passing (32 new: revisions, reviews, activity, storage, options).
- Frontend: `tsc -b` — no new errors (7 pre-existing errors in untouched files
  documented in `RESEARCH.md`).
- Migration: `003_revision_management.py` mirrors the accepted `002` pattern
  (deploy-only; Postgres).
