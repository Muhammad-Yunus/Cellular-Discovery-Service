from fastapi import WebSocket
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self._connections:
            self._connections[channel] = []
        self._connections[channel].append(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self._connections:
            self._connections[channel].remove(websocket)
            if not self._connections[channel]:
                del self._connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def broadcast(self, channel: str, data: dict):
        if channel in self._connections:
            disconnected = []
            for connection in self._connections[channel]:
                try:
                    await connection.send_json(data)
                except Exception:
                    disconnected.append(connection)

            for conn in disconnected:
                self._connections[channel].remove(conn)

    def get_connections_count(self, channel: str) -> int:
        return len(self._connections.get(channel, []))


manager = ConnectionManager()
