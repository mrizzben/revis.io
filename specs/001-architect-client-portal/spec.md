# Feature Specification: Architect-Client Design Portal

**Feature Branch**: `001-architect-client-portal`  
**Created**: 2026-05-09  
**Status**: Draft  
**Input**: User description: "a webapp for architects to present their design to their clients and update their progress realtime based on their latest design files"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Architect Creates Project and Uploads Designs (Priority: P1)

An architect signs up for the platform, creates a new project for a client engagement, and uploads their design files (drawings, renderings, plans, 3D models). The architect can organize these files into milestones or project phases, and then invite their client to view the project.

**Why this priority**: This is the foundation — without project creation and file upload, no other functionality is possible. It delivers immediate standalone value by letting architects centralize their design files for client sharing.

**Independent Test**: Can be fully tested by an architect creating a project, uploading design files, and inviting a client via email. The client receives an invitation and can access the project.

**Acceptance Scenarios**:

1. **Given** an architect is logged in, **When** they create a new project with name and description, **Then** the project appears in their dashboard and is ready for file upload.
2. **Given** a project exists, **When** the architect uploads design files (images, PDFs, or CAD formats), **Then** the files are stored and displayed within the project with appropriate previews.
3. **Given** files have been uploaded to a project, **When** the architect invites a client by email, **Then** the client receives an invitation email with a secure link to access the project.
4. **Given** a project has no files uploaded, **When** the architect views the project, **Then** they see a prompt to upload their first design files.

---

### User Story 2 - Client Views Designs and Receives Real-Time Updates (Priority: P2)

A client accepts the architect's invitation, signs into the platform, and views the latest design files for their project. When the architect uploads new or revised design files, the client sees the updates appear in near real-time without needing to manually refresh the page.

**Why this priority**: This delivers the core value proposition — real-time design progress visibility. It transforms the client experience from email-based file exchanges to an always-up-to-date live view of project progress.

**Independent Test**: Can be fully tested by a client accessing an invited project, viewing existing design files, and observing new files appear automatically when the architect uploads them.

**Acceptance Scenarios**:

1. **Given** a client has received an invitation, **When** they click the invitation link and create an account, **Then** they are taken directly to the project and can view all design files.
2. **Given** a client is viewing a project page, **When** the architect uploads new design files, **Then** the new files appear on the client's screen within 10 seconds without page refresh.
3. **Given** a client is not currently viewing the project, **When** the architect uploads new design files, **Then** the client receives an email or in-app notification about the update.
4. **Given** a client is viewing a project, **When** they click on a design file, **Then** they can see a full preview of the file (image, PDF, or 3D model view).

---

### User Story 3 - Architect Organizes Progress by Milestones (Priority: P3)

An architect structures their project into milestones or phases (e.g., "Concept Design", "Schematic Design", "Design Development"). They associate uploaded design files with specific milestones, mark milestones as complete, and clients can track which phase the project is in and what has been delivered.

**Why this priority**: Provides structure and transparency to the design process, helping clients understand project progress beyond individual files. Valuable but not essential for the basic upload-and-view flow.

**Independent Test**: Can be fully tested by an architect creating milestones within a project, assigning files to milestones, and marking a milestone as complete. The client sees the milestone status update.

**Acceptance Scenarios**:

1. **Given** a project exists, **When** the architect creates milestones with names and descriptions, **Then** they appear as phases in the project timeline visible to the client.
2. **Given** milestones exist, **When** the architect uploads files and assigns them to a specific milestone, **Then** the files are grouped under that milestone for both architect and client views.
3. **Given** a milestone has all its files uploaded, **When** the architect marks the milestone as complete, **Then** the client sees it visually marked as completed in the project timeline.

---

### User Story 4 - Client Provides Feedback on Designs (Priority: P4)

A client reviews design files and provides feedback or comments on specific files or areas within a design. The architect can view and respond to this feedback, creating a structured communication channel tied directly to the design artifacts.

**Why this priority**: Enhances collaboration quality by keeping feedback contextual and organized. Important for project efficiency but the platform delivers value without it through the view-and-update flow.

**Independent Test**: Can be fully tested by a client adding comments on a design file, and the architect viewing and replying to those comments.

**Acceptance Scenarios**:

1. **Given** a client is viewing a design file, **When** they add a comment, **Then** the comment is saved and visible to the architect with a reference to the specific file.
2. **Given** a client has left a comment, **When** the architect responds to the comment, **Then** the client is notified and can view the architect's response.
3. **Given** comments exist on design files, **When** the architect uploads a new version of that file, **Then** previous comments are preserved and linked to the updated file.

---

### Edge Cases

- What happens when a client attempts to access a project they are not invited to? The system must deny access and show an appropriate error message.
- How does the system handle very large design files (e.g., 500MB+ CAD files)? Uploads must support large files with progress indicators, and if a file exceeds the maximum size limit, the user must be informed before upload begins.
- What happens when an architect deletes or replaces a design file that has client comments? Comments should be retained and associated with the file history, not permanently lost.
- How does the system handle an architect inviting the same client to multiple projects? The client should see all their projects in a unified dashboard.
- What happens if a client's invitation link expires? The architect must be able to resend the invitation.
- How does the system handle concurrent uploads from an architect while a client is viewing? Uploads must not interrupt or degrade the client's viewing experience.
- What happens when a client is viewing an older version of a file that the architect just updated? The client should see the update appear without needing to re-navigate.
- How does the system handle project ownership when an architect belongs to a firm? Projects created under a firm account are owned by the firm; if an architect leaves, the firm retains ownership and can reassign the project to another architect within the firm.
- How does the system handle an architect who works independently vs. within a firm? Architects can operate solo without a firm affiliation, or join a firm where all their firm-related projects are owned by the firm.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow architects to create an account using email and password, or via third-party authentication providers.
- **FR-002**: System MUST allow architects to create projects with at minimum a name and optional description.
- **FR-003**: System MUST allow architects to upload design files in common architectural formats, including images (PNG, JPEG, WebP), documents (PDF), and CAD/3D model formats (DWG, DXF, SKP, RVT, IFC, OBJ, STL).
- **FR-004**: System MUST generate visual previews (thumbnails) for uploaded files so clients can browse designs without downloading.
- **FR-005**: System MUST allow architects to invite clients to a project via email, generating a unique secure invitation link.
- **FR-006**: System MUST require invited clients to create an account before accessing project content.
- **FR-007**: System MUST deliver real-time or near-real-time updates to clients when an architect uploads, updates, or removes design files, so clients see changes without manually refreshing.
- **FR-008**: System MUST send notification emails to clients when new design files are uploaded or when milestones are updated, if the client is not actively viewing the project.
- **FR-009**: System MUST allow architects to organize design files into milestones or phases within a project.
- **FR-010**: System MUST allow architects to mark milestones as complete, visually indicating progress to clients.
- **FR-011**: System MUST allow clients to view a project timeline showing milestones and their completion status.
- **FR-012**: System MUST allow clients to add comments on specific design files.
- **FR-013**: System MUST allow architects to view and respond to client comments.
- **FR-014**: System MUST preserve comment history when a design file is updated or replaced.
- **FR-015**: System MUST restrict client access to only projects they have been explicitly invited to.
- **FR-016**: System MUST display a unified dashboard for each user (architect or client) showing all their active projects.
- **FR-017**: System MUST support upload of files up to 1GB in size with visible progress indication.
- **FR-018**: System MUST allow architects to resend expired or lost invitation links to clients.
- **FR-019**: System MUST allow architects to delete or archive projects.
- **FR-020**: System MUST allow architects to optionally create or join a firm account.
- **FR-021**: System MUST ensure that all projects, files, and content created under a firm account are owned by the firm, not the individual architect.
- **FR-022**: System MUST allow firm administrators to reassign projects to other architects within the same firm when an architect leaves or changes roles.

### Constitutional Alignment

- **Ease of Use**: The interface must be intuitive for both architects and clients, with minimal learning curve. Project setup and file upload must be achievable in under 5 minutes for a first-time user. The client view must require no training — clients should understand their project status at a glance.
- **Reactive UI**: State changes (file uploads, milestone completions, comments) must propagate to all connected viewers in near real-time without manual page refreshes. Progress indicators and loading states must provide immediate visual feedback for all async operations.
- **Security**: All project access must be authenticated and authorized. Invitation links must be single-use or time-limited. File downloads must be served through authenticated endpoints, not direct URLs. Client access must be strictly scoped to invited projects only. User passwords must be stored using strong cryptographic hashing.

### Key Entities

- **User**: Represents both architects and clients. Key attributes: email, name, role (architect or client), authentication credentials, optional firm affiliation.
- **Firm**: Represents an architecture firm or organization. Key attributes: name, firm administrators, member architects. Owns all projects created under its scope.
- **Project**: Represents an architectural engagement. Key attributes: name, description, creation date, owning architect and/or owning firm. Linked to invited clients.
- **Design File**: Represents an uploaded design artifact. Key attributes: filename, file type, size, upload date, associated milestone, version history.
- **Milestone**: Represents a phase or deliverable within a project. Key attributes: name, description, position/order, completion status.
- **Comment**: Represents client feedback on a design file. Key attributes: text content, author, creation date, associated design file.
- **Invitation**: Represents a pending client invitation. Key attributes: recipient email, unique token, expiration date, associated project.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can create a project, upload their first design file, and invite a client in under 5 minutes.
- **SC-002**: A client can accept an invitation, create an account, and view project designs in under 3 minutes.
- **SC-003**: When an architect uploads a new design file, clients viewing the project see the update appear within 10 seconds.
- **SC-004**: The system supports simultaneous access for up to 500 concurrent users (architects and clients combined) without noticeable performance degradation.
- **SC-005**: 90% of first-time architects successfully complete project setup and file upload without accessing help documentation.
- **SC-006**: File uploads of up to 100MB complete successfully on standard broadband connections with clear progress feedback; uploads of up to 1GB are supported.
- **SC-007**: Clients report a Net Promoter Score (NPS) of +30 or higher based on ease of viewing and tracking their project's design progress.

## Assumptions

- Users (both architects and clients) have reliable internet connectivity and modern web browsers.
- Initial release is web-only; native mobile applications are out of scope for v1.
- Architects can operate independently or join a firm; projects created under a firm are firm-owned and can be reassigned to other architects within the firm. Solo architects own their projects directly.
- Design file previews (thumbnails and in-browser viewing) will be generated for common formats; exotic or proprietary formats may display as download-only with a file type icon.
- Email delivery for invitations and notifications relies on a third-party email service provider.
- Real-time updates are delivered via a mechanism that works across modern browsers; fallback to polling is acceptable if real-time channels are unavailable.
- File storage and processing costs scale with usage; the platform is expected to handle up to 100GB of total stored files in its initial deployment.
- Clients access the platform primarily via desktop or laptop browsers; responsive design accommodates tablet viewing but mobile phone optimization is secondary.
- Authentication sessions remain valid for a standard duration (e.g., 24 hours) with an option to extend.
- The system will use HTTPS for all communications and enforce secure file transfer protocols.