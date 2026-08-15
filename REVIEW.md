# Review: In-Flight Revision-Management Changes vs TARGETS.md

**Date**: 2026-08-15 · **Scope**: uncommitted work-in-progress on `development`
(new/changed files under `backend/`), reviewed against [`TARGETS.md`](./TARGETS.md).

## Snapshot

Reviewed as-found (other agent still editing the same worktree). Changed/new:

| File | Target | What it adds |
| --- | --- | --- |
| `backend/src/models/file.py` | T1/T2/T7/T8 | `RevisionVisibility`, `ScanStatus`, `content_hash`, `revision_message`, `name`, `description`, `visibility`, `issued_by/at`, `superseded_by/at`, `milestone_id`, `scan_status`, `mime_valid`, `restored_from_superseded` on `FileVersion`; `current_version_id`, `design_option_id`, `parent_file_id` on `DesignFile`; `CLIENT_VISIBLE_VISIBILITIES` |
| `backend/src/models/comment.py` | T1/T3 | `version_id`, `resolved_at`, `resolved_by_id` |
| `backend/src/models/notification.py` | T2/T3 | `review_requested`, `review_updated`, `revision_issued` |
| `backend/src/models/review.py` | T3 | `Review` + `ReviewStatus` (draft/in_review/changes_requested/approved) |
| `backend/src/models/design_option.py` | T5 | `DesignOption` (is_current, is_archived) |
| `backend/src/models/activity.py` | T6 | `ActivityEvent` (append-only, visibility-scoped) |
| `backend/src/services/activity.py` | T6 | `record_event`, `list_events`, `ensure_activity_access` |
| `backend/migrations/versions/003_revision_management.py` | all | schema migration |
| `backend/src/core/config.py` | T8 | `CLAMD_HOST`, `MALWARE_SCAN_MAX_SIZE`, `MULTIPART_ABANDON_AFTER_SECONDS`, `SOFT_DELETE_RETENTION_SECONDS` |
| `backend/src/models/__init__.py` | — | model registry updates |

## Verdict

**DO NOT MERGE — build is red.** The model changes break ORM mapper configuration
and every backend test errors (`31 errors, 0 passed` — the suite was `31 passed`
immediately before these edits landed). This is schema/data-layer work in
progress; nothing in the API, services, or frontend consumes the new fields yet,
so none of the TARGETS "Done when" criteria are met at this point.

## Blocking findings

### F1 (blocker) `Comment.author` / `Comment.resolved_by` — ambiguous join

`comments` now has two FKs to `users` (`author_id`, `resolved_by_id`), but both
relationships omit `foreign_keys`:

```python
author: Mapped["User"] = relationship("User")
resolved_by: Mapped["User | None"] = relationship("User")
```

Result (first mapper configure, every fixture):

```
sqlalchemy.exc.AmbiguousForeignKeysError: Could not determine join condition
between parent/child tables on relationship Comment.author ...
```

Fix:

```python
author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
resolved_by: Mapped["User | None"] = relationship("User", foreign_keys=[resolved_by_id])
```

### F2 (blocker) `FileVersion.uploaded_by` — ambiguous join

`file_versions` now has three FKs to `users` (`uploaded_by_id`, `issued_by_id`,
`superseded_by_id`); `issued_by`/`superseded_by` specify `foreign_keys` but the
pre-existing `uploaded_by` does not. Same `AmbiguousForeignKeysError` once F1 is
fixed:

```python
uploaded_by: Mapped["User"] = relationship("User")  # needs foreign_keys=[uploaded_by_id]
```

Verify with `pytest` — all 31 tests must pass before continuing.

## Coverage vs TARGETS.md

| Target | Status | Evidence / gap |
| --- | --- | --- |
| **T1 File revisions** | ⚠️ schema only | New fields on `FileVersion` + `current_version_id`; but upload still creates a new `DesignFile`, `create_file_version()` is not updated/wired, `version_number` is still hardcoded `1`, no version-list/download/restore endpoints, no revision-scoped comment API. "Done when" unmet. |
| **T2 Checkpoints/issues** | ⚠️ schema only | `name`/`description`/`revision_message`/`issued_*`/`superseded_*` exist; no state machine, no issue/supersede endpoint, no client-visibility transition. |
| **T3 Review workflow** | ⚠️ model + notifications only | `Review` model and statuses match TARGETS exactly; no create/request/decide routes, no reviewer-authorization (internal vs client), no notification fan-out. |
| **T4 Comparison** | ❌ not started | — |
| **T5 Design options** | ⚠️ schema only | `DesignOption` + `design_option_id`/`parent_file_id`; no fork/copy, promote, archive logic, no routes. |
| **T6 Activity/audit** | 🟡 best progress | Append-only `ActivityEvent` + `record_event`/`list_events`/`ensure_activity_access`; no route, and nothing calls `record_event` yet. See N2 below. |
| **T7 Revision visibility** | ⚠️ constants only | `RevisionVisibility` + `CLIENT_VISIBLE_VISIBILITIES` defined; no endpoint filters downloads/previews/WS/search by visibility yet. |
| **T8 Integrity/lifecycle** | ⚠️ columns + config only | `content_hash`/`scan_status`/`mime_valid` columns and clamd/retention config exist; no producer computes hashes, runs scans, or enforces retention/abandoned-multipart cleanup. |

## Non-blocking findings

- **N1 — migration/model dtype drift.** Migration 003 declares `visibility`
  and `scan_status` as `VARCHAR(20)`, while the models use native SQLAlchemy
  enums (`revision_visibility`, `scan_status`). On a Postgres DB created by
  migrations the enum types never exist; `Base.metadata.create_all` (tests) and
  the migration now produce different schemas. Pick one (native enum in both).
- **N2 — activity access is broader than the internal gate.** `ensure_activity_access`
  admits any architect in the owning firm even if they are not a project
  collaborator, and `list_events` only narrows by `role != architect`. A firm
  colleague who was never added to the project team would see the internal
  activity timeline — inconsistent with the 004 "owner + collaborators only"
  gate. Decide explicitly; TARGETS says internal events must never leak to
  clients, not that all firm members are internal to every project.
- **N3 — review/version cross-check not enforced.** `reviews.file_id` and
  `reviews.revision_id` are independent FKs; nothing guarantees the revision
  belongs to the reviewed file, and a review of a client-visible revision vs an
  internal one isn't constrained. Enforce at service level.
- **N4 — idempotency of enum adds.** `ALTER TYPE ... ADD VALUE IF NOT EXISTS`
  is fine, but PG12+ only; README targets PG16 — OK, note it.
- **N5 — `parent_file_id` is untyped provenance.** No FK (intentional for fork
  lineage), fine, but add a comment and index if used for "derived from" queries.

## What's good

- `RevisionVisibility` + `CLIENT_VISIBLE_VISIBILITIES` is exactly the T7 model
  (client sees issued/superseded only).
- `ReviewStatus` matches TARGETS T3 states verbatim.
- Activity design is append-only with per-event visibility, matching T6.
- Circular FK (design_files ↔ file_versions) handled with `use_alter`/late
  constraint adds — correct approach.
- Test suite was green (31 passed) before this change set landed.

## Recommended next steps

1. Fix F1 + F2, get `pytest` green (all 31 tests) — gate for anything else.
2. Wire T1 end to end first (upload → `create_file_version()` with
   `content_hash` → version list/download → restore), since T2/T3/T7 all hang
   off a working version pointer.
3. Add `record_event()` callers for upload/issue/review changes (T6) — cheap and
   makes the audit trail real.
4. Then the T7 filter on download/preview endpoints, then T3 review routes,
   then T5 options.
