"""流式生成管理器 — 将 AI 生成与 WebSocket 生命周期解耦。

目标: 即使用户导航离开（WS 断开），后台 Task 继续运行并持久化消息。
客户端重连后通过 subscribe 获取 replay + 实时事件，恢复流式状态。

多 worker (v6.7): StreamManager 可注入 EventBus。有 bus 时, 后台 Task 的
每个 chunk 同时投递到 bus channel (`arc:stream:{conversation_id}`), 其他
worker 订阅该 channel 把 chunk 转发给自己的 WS 连接。bus=None 时退回纯
进程内模式 (单 worker / 单测默认), 行为与改造前完全一致。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from arc.infrastructure.eventbus import EventBus

logger = logging.getLogger(__name__)

# Session 完成后保留时间（秒），供迟到的重连消费
_RETENTION_SECONDS = 60

# 多 worker 跨进程投递的 channel 前缀
_CHANNEL_PREFIX = "arc:stream:"


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
        self._buffer(event)
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Subscriber queue full for conversation %s, dropping event",
                    self.conversation_id,
                )

    def _buffer(self, event: dict) -> None:
        """只更新 replay buffer 和 full_content, 不投递订阅者。

        多 worker 模式下, 本地订阅者改由 bus 桥接投递 (避免本地 + bus
        双投重复), 故 _run 用 _buffer 维护缓冲, 投递统一走 bus。
        """
        self.events.append(event)
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
    """管理所有活跃的流式生成 session（进程级单例）。

    Args:
        bus: 跨进程事件总线。None = 纯进程内模式 (单 worker / 单测默认,
            行为与改造前一致)。传入 EventBus 则启用多 worker: 后台 Task
            产出的每个 chunk 经 bus 跨进程广播, 其他 worker 的 WS 连接
            通过 bus 收到 chunk。
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._active: dict[str, StreamSession] = {}
        # bus 可显式传入 (测试用), 否则惰性取全局 bus (lifespan 注入)
        self._explicit_bus = bus

    @property
    def _bus(self) -> EventBus | None:
        if self._explicit_bus is not None:
            return self._explicit_bus
        from arc.infrastructure.eventbus import get_global_bus

        return get_global_bus()

    def _channel(self, conversation_id: str) -> str:
        return f"{_CHANNEL_PREFIX}{conversation_id}"

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
        channel = self._channel(conversation_id)
        bus = self._bus

        async def _run():
            try:
                async for event in stream_coro:
                    # 注入 message_id 以保持一致
                    if "message_id" not in event and event.get("content"):
                        event["message_id"] = session.message_id
                    if bus is not None:
                        # 多 worker: 缓冲 + 跨进程广播, 本地订阅者由 bus 桥接投递
                        session._buffer(event)
                        await bus.publish(channel, event)
                    else:
                        # 纯进程内: 缓冲 + 直接投本地 queue
                        session.publish(event)
                session.finish()
                if bus is not None:
                    await bus.publish(channel, {"_sentinel": True})
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
                if bus is not None:
                    await bus.publish(
                        channel, {"type": "error", "detail": str(exc), "_sentinel": True}
                    )
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

        先 replay 已缓冲的事件，再实时读取新事件。多 worker 下, 若注入了
        bus, 跨进程事件经 bus 转发到本地 session.queue, 与本地事件汇合。
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

        # 多 worker: 桥接 bus → session.queue, 使跨进程事件汇入本地订阅者
        bridge_task: asyncio.Task | None = None
        if self._bus is not None:
            bridge_task = asyncio.create_task(
                self._bridge_bus_to_queue(session, q)
            )

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
            if bridge_task is not None:
                bridge_task.cancel()

    async def _bridge_bus_to_queue(
        self, session: StreamSession, target: asyncio.Queue
    ) -> None:
        """把 bus 事件转发到指定 subscriber queue。

        多 worker 模式下, 本地 start_stream 已用 _buffer 维护缓冲 (不再
        直接投本地 queue), 故本地订阅者的实时事件全部来自此桥接 — 无重复。
        """
        if self._bus is None:
            return
        channel = self._channel(session.conversation_id)
        try:
            async for event in self._bus.subscribe(channel):
                if session.done:
                    break
                try:
                    target.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        "Bridge queue full for conversation %s",
                        session.conversation_id,
                    )
        except Exception as exc:
            logger.debug("Bus bridge ended for %s: %s", session.conversation_id, exc)

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
