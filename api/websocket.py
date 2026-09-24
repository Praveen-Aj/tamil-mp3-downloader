"""
WebSocket Connection Manager and Live Event Broadcaster.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and delivers broadcast events."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store running asyncio loop for thread-safe dispatching."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove disconnected client."""
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total clients: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Broadcast JSON payload to all active clients."""
        if not self.active_connections:
            return

        payload = {
            "event": event_type,
            "data": data,
        }
        text_data = json.dumps(payload)
        stale: List[WebSocket] = []

        for connection in list(self.active_connections):
            try:
                await connection.send_text(text_data)
            except Exception:
                stale.append(connection)

        for connection in stale:
            self.active_connections.discard(connection)

    def dispatch_from_thread(self, event_type: str, data: Any) -> None:
        """Thread-safe event dispatch called from background download workers."""
        if self._loop and self._loop.is_running() and self.active_connections:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(event_type, data),
                self._loop,
            )


# Global singleton manager
ws_manager = ConnectionManager()
