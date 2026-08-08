# Research: Kanban Board View

## Drag-and-Drop Approach

**Decision**: Use the `@dnd-kit` library for drag-and-drop.

**Rationale**:
- `@dnd-kit` is the modern, actively maintained successor to `react-beautiful-dnd`
- Lightweight (~15KB gzipped), no DOM layout thrashing
- First-class TypeScript support
- Handles drag-over detection, collision detection, and animations
- Supports the vertical column + horizontal card pattern natively (`DndContext` + `SortableContext`)
- Works with all modern browsers
- No external dependencies beyond React

**Alternatives Considered**:
- **HTML5 Native Drag and Drop**: Built-in, no library cost, but notoriously inconsistent across browsers. No built-in animations, no touch support, poor accessibility.
- **react-beautiful-dnd**: Well-known but deprecated / not maintained. Uses older patterns.
- **react-dnd**: Powerful but verbose API with heavy boilerplate. Overkill for a single drag-and-drop use case.

## PATCH Endpoint Design

**Decision**: Minimal PATCH endpoint on existing file routes.

The endpoint accepts only `milestone_id` as an updatable field. This keeps scope minimal — no full file editing, just milestone reassignment.

## Client Permissions

**Decision**: Reuse existing `require_role("architect")` dependency for the PATCH endpoint. The frontend checks the user role from the auth store to enable/disable drag behavior.

## Testing

- Frontend: Vitest + React Testing Library for component rendering and interaction tests. Mock `@dnd-kit` for drag simulation.
- Backend: pytest + httpx async client for the new PATCH endpoint.