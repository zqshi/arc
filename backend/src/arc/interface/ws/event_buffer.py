"""SSE Event Buffer — 断线重连事件重放。

为每个活跃的 conversation 流保留最近 N 条 SSE 事件的 ring buffer。
客户端断线重连时携带 Last-Event-ID header，服务端从 buffer 重放丢失的事件。

设计考量:
- 纯内存：重启后清空，不做持久化（事件是临时的流数据）
- Per-conversation 隔离：不同对话不共享 buffer
- 线程安全：单进程内靠 asyncio 协程模型保证
- 最大内存占用：200 events × ~2KB/event ≈ 400KB per conversation
- TTL 自动清理：超过 5 分钟未活跃的 buffer 自动回收
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BufferedEvent:
    """A single buffered SSE event with sequence ID."""

    event_id: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.monotonic)


class SSEEventBuffer:
    """Per-conversation ring buffer for SSE event replay.

    Usage:
        buffer = SSEEventBuffer(max_size=200)

        # Producer: 每次发送 SSE 事件时
        event_id = buffer.append({"event": "text_delta", "content": "hello"})
        # → 作为 SSE 的 id: field 发送给客户端

        # Consumer: 客户端重连时
        missed = buffer.replay_from("42")
        # → 返回 event_id > "42" 的所有事件
    """

    def __init__(self, max_size: int = 200):
        self._buffer: deque[BufferedEvent] = deque(maxlen=max_size)
        self._seq: int = 0
        self._last_access: float = time.monotonic()

    @property
    def size(self) -> int:
        """当前缓冲区中的事件数。"""
        return len(self._buffer)

    @property
    def last_access_time(self) -> float:
        """最后一次读写操作的 monotonic 时间戳。"""
        return self._last_access

    def append(self, event: dict[str, Any]) -> str:
        """添加事件到 buffer。

        Args:
            event: SSE event payload (dict)

        Returns:
            分配的 event_id（单调递增的字符串整数）。
        """
        self._seq += 1
        event_id = str(self._seq)
        self._buffer.append(BufferedEvent(event_id=event_id, data=event))
        self._last_access = time.monotonic()
        return event_id

    def replay_from(self, last_event_id: str) -> list[dict[str, Any]]:
        """从 last_event_id 之后重放所有事件。

        Args:
            last_event_id: 客户端最后接收到的 event ID。

        Returns:
            last_event_id 之后的所有事件 payload 列表（按顺序）。
            如果 last_event_id 已被挤出 buffer，返回整个 buffer。
        """
        self._last_access = time.monotonic()

        if not last_event_id:
            return [ev.data for ev in self._buffer]

        try:
            target_seq = int(last_event_id)
        except (ValueError, TypeError):
            return [ev.data for ev in self._buffer]

        # 找到 target_seq 之后的所有事件
        result: list[dict[str, Any]] = []
        for ev in self._buffer:
            if int(ev.event_id) > target_seq:
                result.append(ev.data)

        return result

    @property
    def latest_event_id(self) -> str | None:
        """最新事件的 ID（用于 SSE 初始连接响应）。"""
        if self._buffer:
            return self._buffer[-1].event_id
        return None

    def clear(self) -> None:
        """清空 buffer。"""
        self._buffer.clear()
        self._seq = 0


class SSEEventBufferRegistry:
    """管理所有活跃 conversation 的 event buffer。

    Usage:
        registry = SSEEventBufferRegistry()

        # 获取或创建 buffer
        buffer = registry.get_or_create(conversation_id)
        buffer.append(event)

        # 清理超时 buffer（定期调用）
        registry.cleanup(ttl_seconds=300)
    """

    def __init__(self, default_buffer_size: int = 200):
        self._buffers: dict[str, SSEEventBuffer] = {}
        self._default_size = default_buffer_size

    def get_or_create(self, conversation_id: str) -> SSEEventBuffer:
        """获取已有 buffer 或创建新的。"""
        if conversation_id not in self._buffers:
            self._buffers[conversation_id] = SSEEventBuffer(max_size=self._default_size)
        return self._buffers[conversation_id]

    def get(self, conversation_id: str) -> SSEEventBuffer | None:
        """获取已有 buffer（不创建）。"""
        return self._buffers.get(conversation_id)

    def remove(self, conversation_id: str) -> None:
        """移除 buffer（conversation 结束时）。"""
        self._buffers.pop(conversation_id, None)

    def cleanup(self, ttl_seconds: float = 300) -> int:
        """清理超过 TTL 未活跃的 buffer。

        Args:
            ttl_seconds: 超时秒数（默认 5 分钟）。

        Returns:
            清理的 buffer 数量。
        """
        now = time.monotonic()
        expired = [
            cid for cid, buf in self._buffers.items()
            if now - buf.last_access_time > ttl_seconds
        ]
        for cid in expired:
            del self._buffers[cid]
        return len(expired)

    @property
    def active_count(self) -> int:
        """当前活跃的 buffer 数量。"""
        return len(self._buffers)


# 全局 registry 单例（进程级）
sse_buffer_registry = SSEEventBufferRegistry()
