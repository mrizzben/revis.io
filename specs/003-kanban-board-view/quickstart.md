# Quickstart: Kanban Board View

## What You're Building

A kanban board view on the project management page. Milestones become columns, files become cards. Drag a card to reassign it to a different milestone.

## Files to Create

1. `frontend/src/components/project/KanbanBoard.tsx` — Main board component (fetches milestones + files, renders columns)
2. `frontend/src/components/project/KanbanColumn.tsx` — Single milestone column (accepts droppable cards, shows empty state)
3. `frontend/src/components/project/KanbanCard.tsx` — Single file card (thumbnail, filename, type badge, version, draggable)

## Files to Modify

1. `frontend/src/pages/ProjectManage.tsx` — Add view toggle (Board / Timeline) between milestones section and board
2. `frontend/src/api/endpoints/files.ts` — Add `updateFileMilestone(fileId, milestoneId)` function
3. `backend/src/api/routes/files.py` — Add PATCH `/{file_id}` route for milestone reassignment

## Step-by-Step

### 1. Backend: Add PATCH endpoint

```python
# backend/src/api/routes/files.py
@router.patch("/{file_id}")
async def update_file_milestone(
    file_id: str,
    body: dict,
    db: DBSession,
    current_user: User = Depends(require_role("architect")),
):
    """Update file metadata (milestone_id reassignment for drag-and-drop)."""
    file = await file_service.get_file(db, file_id)
    await project_service._get_project_with_access(db, file.project_id, current_user)

    milestone_id = body.get("milestone_id")
    if milestone_id is not None:
        milestone_result = await db.execute(
            select(Milestone).where(Milestone.id == milestone_id)
        )
        milestone = milestone_result.scalar_one_or_none()
        if not milestone or milestone.project_id != file.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone not found in this project",
            )

    file.milestone_id = milestone_id
    file.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(file)
    return {"milestone_id": file.milestone_id, "updated_at": file.updated_at.isoformat()}
```

### 2. Frontend: Install @dnd-kit

```bash
cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

### 3. Frontend: Create KanbanBoard component

- Fetches milestones and project files via TanStack Query
- Passes the user role to enable/disable drag
- Wraps everything in `DndContext` with collision detection
- Renders columns sorted by milestone position

### 4. Frontend: Create KanbanColumn component

- Renders milestone name header with completion badge
- Uses `useDroppable` from @dnd-kit
- Shows empty state when no cards

### 5. Frontend: Create KanbanCard component

- Thumbnail (reuse existing thumbnail URL logic)
- File name, type badge, version number
- Uses `useSortable` from @dnd-kit if architect, plain div if client

### 6. Frontend: Add view toggle to ProjectManage

- Add a `viewMode` state (`'timeline' | 'board'`)
- Add tab/button bar between the header and milestones section
- Render `<KanbanBoard />` or `<MilestoneTimeline />` based on viewMode
- Import new API function and wire drag-end to `updateFileMilestone` mutation

## Verification

1. Open a project with 2+ milestones, each with files
2. Toggle to Board view → see columns with cards
3. Drag a card to a different column → card moves, milestone assignment persists on reload
4. Toggle back to Timeline → milestone timeline unchanged
5. Open project as client → board visible, drag disabled