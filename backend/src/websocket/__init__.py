from src.websocket.manager import ProjectRoomManager

_manager: ProjectRoomManager | None = None


def set_manager(manager: ProjectRoomManager) -> None:
    global _manager
    _manager = manager


def get_manager() -> ProjectRoomManager:
    if _manager is None:
        raise RuntimeError("WebSocket manager not initialized")
    return _manager
