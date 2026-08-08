# Feature Specification: Kanban Board View

**Feature Branch**: `003-kanban-board-view`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "Render existing milestones as a board with drag-and-drop file cards. Each column is a milestone, each card is a file. Zero backend changes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Architect Views Project as Kanban Board (Priority: P1)

An architect managing a project switches from the timeline view to a board view where milestones are displayed as columns and design files appear as movable cards within those columns. The architect can see at a glance which files belong to which milestone and can drag cards between milestones to reorganize work.

**Why this priority**: This is the core feature — visualizing the existing milestone/file structure as a board. Without this view, the feature doesn't exist. It delivers immediate value by giving architects a kanban-style overview of project progress.

**Independent Test**: Can be fully tested by an architect opening a project that has multiple milestones with files assigned, toggling to the board view, and verifying that columns match milestones and cards match files.

**Acceptance Scenarios**:

1. **Given** a project has 3 milestones ("Concept", "Schematic", "DD") each with 2+ files, **When** the architect switches to board view, **Then** they see 3 columns labeled with milestone names, each containing the files assigned to that milestone.
2. **Given** the board view is displayed, **When** the architect drags a file card from one milestone column to another, **Then** the file is reassigned to the destination milestone and the card moves to that column.
3. **Given** the board view is displayed with more than 4 milestone columns, **When** the architect views the board, **Then** they can scroll horizontally to see all columns.
4. **Given** a milestone has no files assigned, **When** viewing the board, **Then** the column shows an empty state message ("No files in this milestone").

---

### User Story 2 - Architect Toggles Between Timeline and Board View (Priority: P2)

An architect can switch between the existing milestone timeline view and the new kanban board view using a toggle control. The current view preference is visually indicated.

**Why this priority**: Provides the navigation mechanism to access the board. Important but the board itself is the primary value.

**Independent Test**: Can be fully tested by an architect opening a project, clicking the view toggle, and seeing the display switch between timeline and board layouts.

**Acceptance Scenarios**:

1. **Given** an architect is viewing a project's milestone timeline, **When** they click a "Board" toggle/button, **Then** the view switches to the kanban board layout.
2. **Given** an architect is viewing the kanban board, **When** they click a "Timeline" toggle/button, **Then** the view switches back to the milestone timeline layout.
3. **Given** an architect has switched to board view, **When** the page is reloaded, **Then** the view resets to the default timeline view (or persists if state is saved).

---

### User Story 3 - Client Views Project as Read-Only Board (Priority: P3)

A client viewing a shared project can see the board layout with milestones as columns and files as cards, but cannot drag cards or make changes. This provides a visual progress overview.

**Why this priority**: Extends the value to clients but the primary use case is architect workflow.

**Independent Test**: Can be fully tested by a client accessing a project, toggling to board view, seeing the board layout, and verifying that drag attempts don't move cards.

**Acceptance Scenarios**:

1. **Given** a client is viewing a shared project, **When** they toggle to board view, **Then** they see the same column and card layout as the architect.
2. **Given** a client is viewing the board, **When** they attempt to drag a file card, **Then** the card does not move (drag is disabled).
3. **Given** a client views the board, **When** they click a file card, **Then** they are taken to the file viewer/preview just as in the timeline view.

---

### Edge Cases

- What happens when a project has no milestones? The board shows a single "Ungrouped" column or a message prompting the architect to create milestones.
- What happens when a project has no files? All milestone columns appear empty, each showing the empty state message.
- How does the board handle milestones with very long names? Names truncate with ellipsis and show full name on hover/tooltip.
- How does the board handle a file dragged back to its original column? No change occurs — the file stays in its current milestone.
- What happens if a drag operation fails (e.g., network error during the file update)? The card snaps back to its original position and an error message is shown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Architects MUST be able to switch between existing timeline view and a new board view using a toggle control in the project management page.
- **FR-002**: The board view MUST display each milestone as a vertical column with the milestone name as the column header.
- **FR-003**: Each column MUST display all design files assigned to that milestone as file cards.
- **FR-004**: Each file card MUST show the file thumbnail, filename, file type badge, and version number.
- **FR-005**: Architects MUST be able to drag a file card from one milestone column to another.
- **FR-006**: When a file card is dropped on a different milestone column, the file MUST be reassigned to that milestone in the system.
- **FR-007**: Successful file reassignment MUST be visually confirmed (card stays in new column). Failed reassignment MUST return the card to its original position and display an error.
- **FR-008**: Columns with no files MUST display an empty state message.
- **FR-009**: The board MUST support horizontal scrolling when there are more columns than fit on screen.
- **FR-010**: Client users MUST be able to view the board but MUST NOT be able to move file cards between columns.
- **FR-011**: File cards MUST be clickable, opening the file preview/ viewer consistent with the existing file interaction behavior.

### Constitutional Alignment

- **Ease of Use**: The board view provides an intuitive visual layout of project progress. Drag-and-drop reassignment is natural and requires no training. Toggle between views is a single click.
- **Reactive UI**: File cards move immediately on drag completion. Failed operations provide instant visual feedback with card snap-back and error message. The board re-renders dynamically as data changes.
- **Security**: Client users see the same board data but cannot modify milestone assignments. All card movement actions require authenticated architect privileges.

### Key Entities *(include if feature involves data)*

- **Milestone**: Represents a project phase acting as a kanban column. Key attributes: name, position/order, completion status.
- **Design File**: Represents a file card on the board. Key attributes: filename, thumbnail, file type, version number, assigned milestone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can switch from timeline to board view and see all milestones as columns and all files as cards in under 2 seconds.
- **SC-002**: An architect can drag a file card to a different milestone column and see it appear in the new column within 1 second of dropping.
- **SC-003**: A client can view the board in read-only mode — drag-and-drop does not move cards — and can click to preview files.
- **SC-004**: The board view renders correctly for projects with 0 milestones, 1 milestone, and 10+ milestones.
- **SC-005**: Failed file reassignment operations show an error and return the card to its original position.

## Assumptions

- Milestones already exist in the system with ordered positions and files already assigned to milestones (this feature does not create milestones or upload files).
- The existing file reassignment functionality (updating which milestone a file belongs to) continues to work correctly.
- User roles (architect vs. client) are already defined and the feature uses the existing role check to enable/disable drag behavior.
- The timeline view remains the default; board view is a toggle option.
- View preference does not need to persist across page reloads initially — it resets to timeline on reload.
- Existing thumbnail generation is sufficient — no new thumbnail sizes or formats are needed.
