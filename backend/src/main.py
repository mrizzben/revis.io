"""FastAPI application entry point."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.router import api_router
from src.core.config import settings
from src.core.logging import logging_middleware, setup_logging
from src.services import maintenance as maintenance_service
from src.websocket import set_manager
from src.websocket.handlers import ws_connect
from src.websocket.manager import ProjectRoomManager

logger = logging.getLogger(__name__)

ws_manager = ProjectRoomManager()
set_manager(ws_manager)

# Small initial delay so a freshly restarted instance doesn't run maintenance
# at the same moment other instances are starting up.
_MAINTENANCE_STARTUP_DELAY_SECONDS = 60


async def _storage_maintenance_loop() -> None:
    """Periodic storage maintenance background task (T8).

    Aborts abandoned multipart uploads and purges expired soft-deleted items.
    A failed run is logged but never kills the loop.
    """
    # ponytail: single-app-instance scheduler; move to a dedicated beat
    # process if multiple instances run
    await asyncio.sleep(_MAINTENANCE_STARTUP_DELAY_SECONDS)
    while True:
        try:
            from src.core.database import async_session_factory

            async with async_session_factory() as db:
                report = await maintenance_service.run_maintenance(db)
            logger.info("Storage maintenance complete: %s", report)
        except Exception:
            logger.exception("Storage maintenance run failed")
        await asyncio.sleep(settings.STORAGE_MAINTENANCE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown events."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Revis.io API starting")

    # Ensure RustFS bucket exists
    from src.services.file import ensure_bucket_exists

    await ensure_bucket_exists()

    task = asyncio.create_task(_storage_maintenance_loop())

    yield

    # Shutdown
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    logger.info("Revis.io API shutting down")
    from src.core.database import engine

    await engine.dispose()


app = FastAPI(
    title="Revis.io API",
    version="1.0.0",
    description="Architect-Client Design Portal — REST + WebSocket API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP logging middleware (outermost to capture all requests)
app.middleware("http")(logging_middleware)


# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions."""
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=True,
    )

    # Create response
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

    # Add CORS headers
    origin = request.headers.get("origin")
    if origin and origin in settings.CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    elif "*" in settings.CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"

    return response


# WebSocket endpoint
@app.websocket("/ws/projects/{project_id}")
async def project_websocket(
    websocket: WebSocket,
    project_id: int,
    token: str = Query(...),
) -> None:
    await ws_connect(websocket, project_id, token, ws_manager)


# Include the API router
app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
