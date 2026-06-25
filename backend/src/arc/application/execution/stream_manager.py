"""流式生成管理器 — 将 AI 生成与 WebSocket 生命周期解耦。

目标: 即使用户导航离开（WS 断开），后台 Task 继续运行并持久化消息。
客户端重连后通过 subscribe 获取 replay + 实时事件，恢复流式状态。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Session 完成后保留时间（秒），供迟到的重连消费
_RETENTION_SECONDS = 60


@dataclass
class StreamSession:
    """单次流式生成的服务端状态。"""

    conversation_id: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    events: list[dict] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    full_content: str = ""
    task: asyncio.Task | None = field(default=None, repr=False)
    _subscribers: list[asyncio.Queue] = field(default_factory=list, repr=False)
    _finished_at: float | None = field(default=None, repr=False)

    def publish(self, event: dict) -> None:
        """发布事件到所有订阅者，同时存入 replay buffer。"""
        self.events.append(event)
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Subscriber queue full for conversation %s, dropping event",
                    self.conversation_id,
                )

        # 累积文本内容，用于中断时保存部分内容
        content = event.get("content", "")
        if content and event.get("type") != "error":
            self.full_content += content

    def finish(self, *, error: str | None = None) -> None:
        """标记 session 完成。"""
        self.done = True
        self.error = error
        self._finished_at = time.monotonic()
        # 发送终止哨兵让所有订阅者退出
        sentinel: dict = {"_sentinel": True}
        for q in self._subscribers:
            try:
                q.put_nowait(sentinel)
            except asyncio.QueueFull:
                pass

    def add_subscriber(self) -> asyncio.Queue:
        """创建并返回一个新的订阅队列。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue) -> None:
        """移除订阅队列。"""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    @property
    def is_expired(self) -> bool:
        if not self.done or self._finished_at is None:
            return False
        return (time.monotonic() - self._finished_at) > _RETENTION_SECONDS


class StreamManager:
    """管理所有活跃的流式生成 session（进程级单例）。"""

    def __init__(self) -> None:
        self._active: dict[str, StreamSession] = {}

    def get_session(self, conversation_id: str) -> StreamSession | None:
        """获取指定对话的活跃/最近完成的 session。"""
        session = self._active.get(conversation_id)
        if session and session.is_expired:
            del self._active[conversation_id]
            return None
        return session

    def start_stream(
        self,
        conversation_id: str,
        stream_coro,
        *,
        on_complete=None,
        on_error=None,
    ) -> StreamSession:
        """启动后台流式生成任务。

        Args:
            conversation_id: 对话 ID
            stream_coro: 产出事件 dict 的异步生成器
            on_complete: 流完成后回调 async fn(session)
            on_error: 流异常后回调 async fn(session, exception)

        Returns:
            StreamSession 实例，调用方可用于 subscribe。
        """
        # 如果已有活跃 session，不重复启动
        existing = self.get_session(conversation_id)
        if existing and not existing.done:
            logger.info(
                "Stream already active for conversation %s, reusing",
                conversation_id,
            )
            return existing

        session = StreamSession(conversation_id=conversation_id)
        self._active[conversation_id] = session

        async def _run():
            try:
                async for event in stream_coro:
                    # 注入 message_id 以保持一致
                    if "message_id" not in event and event.get("content"):
                        event["message_id"] = session.message_id
                    session.publish(event)
                session.finish()
                if on_complete:
                    await on_complete(session)
            except Exception as exc:
                logger.error(
                    "Stream error for conversation %s: %s",
                    conversation_id,
                    exc,
                    exc_info=True,
                )
                session.publish({"type": "error", "detail": str(exc)})
                session.finish(error=str(exc))
                if on_error:
                    await on_error(session, exc)

        session.task = asyncio.create_task(_run())
        logger.info("Started stream for conversation %s", conversation_id)
        return session

    async def subscribe(
        self,
        session: StreamSession,
    ) -> AsyncIterator[dict]:
        """订阅 session 的事件流。

        先 replay 已缓冲的事件，再实时读取新事件。
        """
        # Phase 1: Replay — 快照当前 events 长度后逐条 yield
        snapshot_len = len(session.events)
        for event in session.events[:snapshot_len]:
            yield event

        # 如果 session 已完成，不需要实时监听
        if session.done:
            return

        # Phase 2: Live — 通过 queue 接收新事件
        q = session.add_subscriber()
        try:
            # 补发 replay 快照后到注册 subscriber 之间可能产生的事件
            for event in session.events[snapshot_len:]:
                yield event

            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # 心跳超时保护，session 若已完成则退出
                    if session.done:
                        break
                    continue

                if event.get("_sentinel"):
                    break
                yield event
        finally:
            session.remove_subscriber(q)

    def cleanup_expired(self) -> int:
        """清理过期 session。返回清理数量。"""
        expired = [
            cid
            for cid, s in self._active.items()
            if s.is_expired
        ]
        for cid in expired:
            del self._active[cid]
        return len(expired)


# 进程级单例
stream_manager = StreamManager()
