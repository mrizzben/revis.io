import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import decode_token
from src.models.project import Project, ProjectMember
from src.models.user import User


class ProjectRoomManager:
    """In-process WebSocket connection manager with Redis PUB/SUB fanout."""

    def __init__(self) -> None:
        self._connections: dict[int, dict[int, WebSocket]] = {}
        self._redis: aioredis.Redis | None = None
        self._subscriber_task: asyncio.Task[Any] | None = None
        self._heartbeat_task: asyncio.Task[Any] | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL)
            self._subscriber_task = asyncio.create_task(self._subscribe_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return self._redis

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            for project_id, users in list(self._connections.items()):
                for user_id, ws in list(users.items()):
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        await self.disconnect(project_id, user_id)

    async def _subscribe_loop(self) -> None:
        redis = await self._get_redis()
        pubsub = redis.pubsub()
        await pubsub.psubscribe("project:*")
        try:
            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data_str = message["data"]
                if isinstance(data_str, bytes):
                    data_str = data_str.decode()
                if channel.startswith("project:"):
                    project_id = int(channel.split(":", 1)[1])
                    try:
                        payload = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    await self._send_to_local(project_id, payload)
        except asyncio.CancelledError:
            await pubsub.unsubscribe()

    async def _send_to_local(self, project_id: int, message: dict) -> None:
        users = self._connections.get(project_id, {})
        exclude = message.pop("_exclude_user_id", None)
        allow = message.pop("_allow_user_ids", None)
        for user_id, ws in list(users.items()):
            if exclude is not None and user_id == exclude:
                continue
            if allow is not None and user_id not in allow:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(project_id, user_id)

    async def connect(self, project_id: int, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        if project_id not in self._connections:
            self._connections[project_id] = {}
        self._connections[project_id][user_id] = websocket

    async def disconnect(self, project_id: int, user_id: int) -> None:
        room = self._connections.get(project_id)
        if room:
            ws = room.pop(user_id, None)
            if ws:
                try:
                    await ws.close(code=1000)
                except Exception:
                    pass
            if not room:
                del self._connections[project_id]

    async def broadcast_to_project(
        self, project_id: int, message: dict, exclude_user_id: int | None = None
    ) -> None:
        """Broadcast to every connected user in the project room (all roles)."""
        redis = await self._get_redis()
        payload = dict(message)
        if exclude_user_id is not None:
            payload["_exclude_user_id"] = exclude_user_id
        channel = f"project:{project_id}"
        await redis.publish(channel, json.dumps(payload))

    async def broadcast_to_project_team(
        self,
        project_id: int,
        message: dict,
        team_user_ids: list[int],
        exclude_user_id: int | None = None,
    ) -> None:
        """Broadcast to a restricted set of users in the project room.

        Internal collaboration events must never reach client-role connections,
        so the payload carries the allowlist and the local dispatcher filters it.
        """
        redis = await self._get_redis()
        payload = dict(message)
        payload["_allow_user_ids"] = team_user_ids
        if exclude_user_id is not None:
            payload["_exclude_user_id"] = exclude_user_id
        channel = f"project:{project_id}"
        await redis.publish(channel, json.dumps(payload))

    async def send_to_user(self, project_id: int, user_id: int, message: dict) -> None:
        room = self._connections.get(project_id, {})
        ws = room.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(project_id, user_id)

    def get_project_connections(self, project_id: int) -> list[int]:
        room = self._connections.get(project_id, {})
        return list(room.keys())


async def verify_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    client_project_id: int | None = None,
) -> bool:
    """Check if a user has access to a project (owner or member, not archived).

    Anonymous client sessions pass their scoped ``client_project_id``; they
    are granted access only while the project's client access is still enabled.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.is_archived.is_(False),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return False

    if project.owner_id == user_id:
        return True

    if client_project_id is not None:
        return client_project_id == project_id and project.client_token is not None

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return member_result.scalar_one_or_none() is not None


async def validate_ws_token(token: str) -> dict:
    """Validate JWT token string and return payload. Raises on failure."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("Invalid token type")
    return payload


async def get_user_from_payload(db: AsyncSession, payload: dict) -> User | None:
    """Fetch user from DB by token payload sub."""
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.scalar_one_or_none()
