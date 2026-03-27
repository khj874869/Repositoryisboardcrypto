from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class Broadcaster:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps(
            {
                'type': message_type,
                'payload': payload,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        stale: list[WebSocket] = []
        async with self._lock:
            for websocket in self._connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    stale.append(websocket)
            for websocket in stale:
                self._connections.discard(websocket)
