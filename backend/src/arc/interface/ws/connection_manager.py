"""WebSocket connection manager — tracks active connections per conversation.

多 worker (v6.7): 注入 EventBus 后, broadcast 既发给本地连接又 publish 到
bus channel `arc:conn:{conversation_id}`; 后台订阅 bus 把跨进程事件转发到
本 worker 的本地连接。bus=None 时退回纯进程内模式 (单 worker / 单测默认)。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from arc.infrastructure.eventbus import EventBus

logger = logging.getLogger(__name__)

_CHANNEL_PREFIX = "arc:conn:"


class ConnectionManager:
    def __init__(self, bus: EventBus | None = None):
        self.active: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._explicit_bus = bus
        self._bridge_tasks: dict[str, asyncio.Task] = {}

    @property
    def _bus(self) -> EventBus | None:
        if self._explicit_bus is not None:
            return self._explicit_bus
        from arc.infrastructure.eventbus import get_global_bus

        return get_global_bus()

    def _channel(self, conversation_id: str) -> str:
        return f"{_CHANNEL_PREFIX}{conversation_id}"

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.setdefault(conversation_id, []).append(ws)
            # 首个本地连接时启动 bus 桥接 (有 bus 才启)
            if self._bus is not None and conversation_id not in self._bridge_tasks:
                self._bridge_tasks[conversation_id] = asyncio.create_task(
                    self._bridge_bus_to_local(conversation_id)
                )

    async def disconnect(self, conversation_id: str, ws: WebSocket):
        async with self._lock:
            conns = self.active.get(conversation_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self.active.pop(conversation_id, None)
                task = self._bridge_tasks.pop(conversation_id, None)
        # 无本地连接后停止桥接 (锁外 cancel 避免死锁)
        if not self.active.get(conversation_id) and task:
            task.cancel()

    async def broadcast(self, conversation_id: str, data: dict):
        if self._bus is not None:
            # 多 worker: 统一经 bus, 本地连接由桥接投递 (无重复)
            await self._bus.publish(self._channel(conversation_id), data)
        else:
            # 纯进程内: 直接发本地连接
            await self._send_local(conversation_id, data)

    async def _send_local(self, conversation_id: str, data: dict) -> None:
        """发给本 worker 的本地 WS 连接, 清理失效连接。"""
        async with self._lock:
            conns = list(self.active.get(conversation_id, []))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(conversation_id, ws)

    async def _bridge_bus_to_local(self, conversation_id: str) -> None:
        """订阅 bus channel, 把跨进程事件转发到本地连接。

        本地 broadcast 已直接发本地连接, bus 回环的事件对本地是重复,
        故桥接跳过本地自己刚发的事件 — 用 data 不可哈希无法精确去重,
        改为: 桥接只处理"其他 worker 发来的"。由于 InMemory bus 回环
        也会触发本地订阅, 此处接受偶发重复 (WS 客户端对重复 message
        事件幂等性可接受, 真实跨 worker 场景下无重复)。
        """
        if self._bus is None:
            return
        channel = self._channel(conversation_id)
        try:
            async for event in self._bus.subscribe(channel):
                if not self.active.get(conversation_id):
                    break
                await self._send_local(conversation_id, event)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("Conn bridge ended for %s: %s", conversation_id, exc)


manager = ConnectionManager()
