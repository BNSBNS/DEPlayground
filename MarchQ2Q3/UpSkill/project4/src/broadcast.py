from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket

from src.logging import get_logger

log = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts JSON messages."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        log.info("ws_connected", total=len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        log.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send JSON to all connected clients, removing dead connections."""
        dead: list[WebSocket] = []
        message = json.dumps(data, default=str)

        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global managers for different streams
sales_manager = ConnectionManager()
events_manager = ConnectionManager()
