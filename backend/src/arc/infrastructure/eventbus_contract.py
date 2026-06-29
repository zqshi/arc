"""EventBus contract shared by in-memory and Redis implementations."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

_DEFAULT_REPLAY_SIZE = 500


@runtime_checkable
class EventBus(Protocol):
    """事件总线抽象。实现方保证 publish/subscribe/shutdown 语义一致。"""

    async def publish(self, channel: str, event: dict) -> None:
        """投递事件到 channel 的所有订阅者, 并写入 replay 缓冲。"""
        ...

    def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """订阅 channel: 先重放历史事件, 再接收实时事件, 直到 shutdown。"""
        ...

    async def shutdown(self) -> None:
        """通知所有订阅者终止, 释放资源。"""
        ...

