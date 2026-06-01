"""WebSocket connection manager — tracks active connections per conversation."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.setdefault(conversation_id, []).append(ws)

    async def disconnect(self, conversation_id: str, ws: WebSocket):
        async with self._lock:
            conns = self.active.get(conversation_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self.active.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, data: dict):
        dead: list[WebSocket] = []
        async with self._lock:
            conns = list(self.active.get(conversation_id, []))
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(conversation_id, ws)


manager = ConnectionManager()
