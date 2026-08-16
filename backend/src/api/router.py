"""API router aggregation — imports and includes all route modules."""

from fastapi import APIRouter

from src.api.routes import (
    activity,
    auth,
    client_access,
    collaborators,
    comments,
    files,
    firms,
    internal_notes,
    invitations,
    milestones,
    notifications,
    options,
    projects,
    reviews,
    storage,
    todos,
    users,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(firms.router, tags=["Firms"])
api_router.include_router(projects.router, tags=["Projects"])
api_router.include_router(invitations.router, tags=["Invitations"])
api_router.include_router(client_access.router, tags=["Client Access"])
api_router.include_router(files.router, tags=["Files"])
api_router.include_router(milestones.router, tags=["Milestones"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(comments.router, tags=["Comments"])
api_router.include_router(collaborators.router, tags=["Collaborators"])
api_router.include_router(internal_notes.router, tags=["Internal Notes"])
api_router.include_router(todos.router, tags=["To-Dos"])
api_router.include_router(reviews.router, tags=["Reviews"])
api_router.include_router(activity.router, tags=["Activity"])
api_router.include_router(storage.router, tags=["Storage"])
api_router.include_router(options.router, tags=["Design Options"])
