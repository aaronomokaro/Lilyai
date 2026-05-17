import json
from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Maps user_id to their active WebSocket connection
        # TODO: Support multiple tabs per user by mapping user_id to List[WebSocket]
        # Current implementation overwrites previous connection when a new tab connects.
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict) -> None:
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                self.disconnect(user_id)

    async def send_document_ready(
        self, user_id: str, document_id: str, filename: str
    ) -> None:
        await self.send_to_user(
            user_id=user_id,
            message={
                "event": "document_ready",
                "document_id": document_id,
                "filename": filename,
                "status": "ready",
            },
        )

    async def send_document_failed(
        self, user_id: str, document_id: str, filename: str
    ) -> None:
        await self.send_to_user(
            user_id=user_id,
            message={
                "event": "document_failed",
                "document_id": document_id,
                "filename": filename,
                "status": "failed",
            },
        )


manager = ConnectionManager()
