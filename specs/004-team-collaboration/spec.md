# Feature Specification: Internal Team Collaboration

**Feature Branch**: `004-team-collaboration`  
**Created**: 2026-08-08  
**Status**: Draft  
**Input**: User description: "Internal team collaboration — add collaborators to a project, internal-only notes/@mentions hidden from clients, assignable to-dos | Closes the collaborate internally half of the goal; biggest gap"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Architect Adds Internal Collaborators to a Project (Priority: P1)

An architect working on a project adds one or more team members (other architects/designers within their firm, or co-workers on the engagement) as internal collaborators. Each collaborator can access the project's internal workspace: view the project, add internal notes, be mentioned, and be assigned to-dos. Collaborators never see client-only or external-facing restrictions, and clients never see the internal workspace.

**Why this priority**: This is the foundation of internal team collaboration. Without a way to add collaborators, no internal notes, mentions, or to-dos can involve more than the project owner. It delivers immediate value by letting a team work on a project together.

**Independent Test**: Can be fully tested by an architect inviting a second team member to a project and verifying that the invited member can open the project and access its internal workspace (notes, to-dos), while a client on the same project sees no trace of the collaborator or the internal workspace.

**Acceptance Scenarios**:

1. **Given** a project exists and the architect is its owner, **When** the architect adds a team member as an internal collaborator, **Then** the invited member appears as a collaborator on the project and can access the internal workspace.
2. **Given** a collaborator has been added, **When** they open the project, **Then** they can view the project and the internal workspace (internal notes and to-dos), but cannot see or modify client-facing access beyond what their role allows.
3. **Given** a client is viewing the same project, **When** they open the project, **Then** they see only the external-facing content and have no indication that collaborators or internal notes/to-dos exist.
4. **Given** the project owner, **When** they remove a collaborator from the project, **Then** the removed member loses access to the project's internal workspace immediately.

---

### User Story 2 - Team Shares Internal Notes with @Mentions (Priority: P2)

Team members working on a project create internal notes visible only to the project's collaborators and owner. Notes support @mentions to flag specific team members. The mentioned member is notified and can reply. All internal notes and mentions are completely hidden from clients.

**Why this priority**: This is the primary day-to-day collaboration mechanism — capturing decisions, context, and flagging teammates. It delivers value on its own once collaborators exist. It is the core of the "collaborate internally" goal.

**Independent Test**: Can be fully tested by a collaborator creating an internal note with an @mention of another collaborator, verifying the mentioned member is notified and can reply, and confirming a client viewing the project sees none of the notes.

**Acceptance Scenarios**:

1. **Given** a project with multiple collaborators, **When** one collaborator creates an internal note, **Then** the note is saved and visible to the project owner and all collaborators, but not to clients.
2. **Given** a collaborator is writing an internal note, **When** they type "@" and select another collaborator's name, **Then** that member is notified about the mention.
3. **Given** an internal note with an @mention, **When** the mentioned member opens the project, **Then** they see a notification or indicator that they were mentioned and can open the note.
4. **Given** a collaborator views an internal note, **When** they add a reply, **Then** the reply is appended to the note and visible only to the internal team.
5. **Given** a client views the same project, **When** they browse project content, **Then** no internal notes, mentions, or collaborator names are visible anywhere in the client-facing view.

---

### User Story 3 - Team Assigns and Tracks To-Dos (Priority: P3)

Team members create to-dos within a project and assign them to specific collaborators. Assigned members see their assigned to-dos, can mark them complete, and the team can track overall progress. To-dos are internal-only and never shown to clients.

**Why this priority**: Adds lightweight task tracking that keeps the internal team aligned on deliverables. Valuable for coordination but secondary to sharing notes; the platform remains useful for collaboration without formal task tracking.

**Independent Test**: Can be fully tested by a collaborator creating a to-do, assigning it to another collaborator, the assignee completing it, and verifying the client never sees the to-do.

**Acceptance Scenarios**:

1. **Given** a project with collaborators, **When** a collaborator creates a to-do and assigns it to another collaborator, **Then** the to-do appears in the project's internal workspace assigned to the selected member.
2. **Given** a to-do assigned to a member, **When** the assignee marks it complete, **Then** the to-do shows as complete and the change is visible to the internal team.
3. **Given** a to-do, **When** it is edited, reassigned, or deleted by an internal team member, **Then** the change is reflected for the internal team.
4. **Given** a client views the project, **When** they browse project content, **Then** no to-dos or their completion status are visible.

---

### Edge Cases

- What happens when a client belongs to the same firm as the collaborators? Client role still restricts them from the internal workspace; client access is controlled by their role on the specific project, not firm membership.
- What happens when a collaborator is removed while they have open assigned to-dos or mentions? Their to-dos should be reassigned or made visible to the owner; their mentions are hidden from clients but the note content remains for the internal team.
- How does the system handle when the project owner leaves or there is no owner? Internal content remains with the firm/project ownership model already defined for firm-owned projects.
- What happens when a collaborator re-joins a project after removal? They regain access to the current internal workspace state.
- How does the system handle internal notes if a design file they mention is later deleted? Note text and replies are preserved for the project lifetime (notes are project-scoped in v1).
- What happens when an @mention targets a user who is not yet a collaborator on the project? The system should either restrict mention to existing collaborators or add the mentioned user and/or prompt the owner to add them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the project owner to add users as internal collaborators on a project.
- **FR-002**: System MUST allow the project owner to remove collaborators from a project, revoking their internal access immediately.
- **FR-003**: System MUST allow collaborators to access the project's internal workspace (internal notes and to-dos).
- **FR-004**: System MUST keep all internal collaboration content (notes, replies, mentions, to-dos, collaborator names) hidden from clients and anyone not granted internal access to that project, and MUST exclude it from all client-facing views.
- **FR-005**: System MUST allow collaborators to create internal notes on a project.
- **FR-006**: System MUST allow collaborators to reply to internal notes.
- **FR-007**: System MUST support @mentions in internal notes that reference project collaborators and generate a notification to the mentioned member.
- **FR-008**: System MUST allow collaborators to create to-dos within a project.
- **FR-009**: System MUST allow collaborators to assign a to-do to a specific collaborator.
- **FR-010**: System MUST allow collaborators to update the status of a to-do (e.g., open/complete) and MUST propagate those updates to connected team members without manual page refresh.
- **FR-011**: System MUST allow all internal team members (owner and collaborators) to edit, reassign, or delete project to-dos.
- **FR-012**: System MUST provide a notification mechanism (in-app and/or email) for @mentions and to-do assignments, only to internal team members.
- **FR-013**: System MUST preserve internal notes, replies, and mentions for the life of the project; because notes are project-scoped in v1 (not associated with design files), design-file updates do not affect them.

### Constitutional Alignment

- **Ease of Use**: Adding a collaborator, writing an internal note with a mention, and assigning a to-do must be quick and intuitive for architects — discoverable within the project without training. The internal workspace should be clearly separated from the client-facing view so users never confuse the two.
- **Reactive UI**: Internal notes, replies, mentions, and to-do status changes must propagate to connected internal team members in near real-time without manual refresh, matching the platform's existing reactive behavior.
- **Security**: Internal collaboration content must be authorization-scoped to the project's collaborators and owner, and must never leak to the client-facing view or to any user without internal access to that project. Role separation (internal vs. client) must be enforced at all access points.

### Key Entities

- **Collaborator**: A user granted internal access to a project. Key attributes: user, project, role within the project (owner or collaborator), date added, date removed.
- **Internal Note**: An internal-only annotation on a project. Key attributes: text content, author, creation date, replies. Project-scoped in v1 (file association deferred). Visible only to the project's internal team.
- **Mention**: A reference to a collaborator within an internal note. Key attributes: mentioned user, note, notification status.
- **To-Do**: An internal task within a project. Key attributes: title, description, assignee, status (open/complete), creation date, creator.
- **Project**: Existing entity, now enriched with an internal collaborators list and internal workspace.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A project owner can add a collaborator, and that collaborator can access the internal workspace in under 2 minutes from the moment the owner begins.
- **SC-002**: A collaborator can create an internal note with an @mention in under 1 minute.
- **SC-003**: An @mention or to-do assignment notification reaches the intended internal team member within 10 seconds when they are active on the platform.
- **SC-004**: In automated role-based testing, zero internal notes, replies, mentions, to-do items, or collaborator names appear in client-facing views across all flows.
- **SC-005**: Internal note and to-do updates are visible to connected team members within 10 seconds without a manual page refresh.
- **SC-006**: 90% of first-time collaborators successfully add a note, mention a teammate, and use a to-do without accessing help documentation.

## Assumptions

- Collaborators are internal team members (users within the owning firm or explicitly added co-workers), not clients. Client access remains governed by the existing invitation/role model, and clients are always excluded from internal content regardless of firm membership.
- The project has exactly one owner who manages collaborator membership; existing firm ownership rules (firm owns projects) continue to apply.
- Internal collaboration content (notes, replies, mentions, to-dos) is scoped to a single project and its internal team; there is no cross-project internal feed in this feature.
- Notifications for mentions and to-do assignments reuse the platform's existing notification/email mechanisms; no new notification channel is required.
- Internal notes are project-scoped in v1 and may be associated with a design file in a later iteration; note and reply text is preserved for the project lifetime, and file-deletion handling follows existing comment-preservation behavior.
- Real-time propagation for internal content uses the same mechanism as existing project updates, with polling fallback acceptable.
- This feature adds internal collaboration on top of existing architect↔client flows; it does not change client-facing behavior or permissions.
