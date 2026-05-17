import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from src.core.database import async_session_factory
from src.websocket.manager import (
    ProjectRoomManager,
    get_user_from_payload,
    validate_ws_token,
    verify_project_access,
)


async def ws_connect(
    websocket: WebSocket,
    project_id: int,
    token: str,
    manager: ProjectRoomManager,
) -> None:
    payload = await validate_ws_token(token)

    async with async_session_factory() as db:
        user = await get_user_from_payload(db, payload)
        if user is None:
            await websocket.close(code=4001, reason="Authentication failed")
            return

        has_access = await verify_project_access(db, project_id, user.id)
        if not has_access:
            await websocket.close(code=4003, reason="Access denied")
            return

    await manager.connect(project_id, user.id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg: dict[str, Any] = json.loads(data)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(project_id, user.id)
