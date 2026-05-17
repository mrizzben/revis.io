"""API router aggregation — imports and includes all route modules."""

from fastapi import APIRouter

from src.api.routes import auth, comments, firms, files, invitations, milestones, notifications, projects, users

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(firms.router, tags=["Firms"])
api_router.include_router(projects.router, tags=["Projects"])
api_router.include_router(invitations.router, tags=["Invitations"])
api_router.include_router(files.router, tags=["Files"])
api_router.include_router(milestones.router, tags=["Milestones"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(comments.router, tags=["Comments"])
