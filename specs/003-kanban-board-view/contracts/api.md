# API Contracts: Kanban Board View

## PATCH /api/files/{file_id}

Update a file's milestone assignment (drag-and-drop reassignment).

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `milestone_id` | integer | Yes | The milestone to assign the file to. Pass `null` to unassign. |

### Response (200)

Returns the updated file object matching the existing `DesignFile` schema.

### Authorization

Architect only (`require_role("architect")`). Project access verified via existing `_get_project_with_access`.

### Validation

- File must exist and not be soft-deleted
- Milestone must exist and belong to the same project as the file
- If `milestone_id` is `null`, the file is unassigned from any milestone

### Example

```
PATCH /api/files/abc-123-def
{
  "milestone_id": 5
}
```