# Data Model: Kanban Board View

No new entities, tables, or schema changes required.

## Existing Entities Used

| Entity | Usage in Board View |
|--------|-------------------|
| `Milestone` | Rendered as a board column. `position` determines left-to-right column order. `name` is the column header. `is_completed` shown as a visual indicator. |
| `DesignFile` | Rendered as a card within a column. `milestone_id` determines which column the card appears in. `filename`, `file_type`, `file_size`, `thumbnail_status` used for card display. `version_number` shown on card. |

## Changes

### New Field on DesignFile (optional, Phase B)

```python
# If review status is added later (not in scope for v1):
review_status: "pending" | "in_review" | "approved"  # default: "pending"
```

Not required for the board view MVP. The board works with existing `milestone_id` alone.