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

### T1 — File revisions

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

1. **T1 — File revisions**
2. **T2 — Named checkpoints and issues**
3. **T3 — Review workflow**
4. **T6 — Activity and audit history**
5. **T7 — Revision-level visibility and permissions**
6. **T4 — PDF/image comparison**
7. **T8 — File integrity and storage lifecycle**
8. **T5 — Design options**

The first three targets create the core product loop:

```text
upload revision → review → issue to client → supersede or restore
```

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
