"""OpenSandbox 沙箱注册表 (v6.7 全量多 worker)。

跨 worker 共享 sandbox_id: OpenSandbox SDK 的 Sandbox 实例持有远程连接
不可跨进程, 但 sandbox_id (字符串) 可存 Redis 共享。各 worker 用
Sandbox.connect(id) resume 同一远程沙箱, 实现全量多 worker。

存储: Redis key `arc:sandbox-id:{conversation_id}` → sandbox_id, TTL 与
沙箱生命周期一致。无 Redis (单 worker) 时退回进程内 dict。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.infrastructure.eventbus import EventBus

logger = logging.getLogger(__name__)

_KEY_PREFIX = "arc:sandbox-id:"
_TTL_SECONDS = 600  # 与沙箱 timeout 对齐


class SandboxRegistry:
    """跨 worker 的 sandbox_id 共享 (Redis 或进程内降级)。"""

    def __init__(self, bus: EventBus | None = None):
        self._explicit_bus = bus
        self._local: dict[str, str] = {}  # 进程内降级 (无 Redis)

    @property
    def _redis(self):
        """取 Redis 连接 (复用 EventBus 的 RedisEventBus 内部连接)。

        EventBus 抽象不暴露底层 Redis, 故此处直接取全局 bus 的 _redis
        (仅 RedisEventBus 有; InMemory 返回 None → 降级进程内)。
        """
        if self._explicit_bus is not None:
            bus = self._explicit_bus
        else:
            try:
                from arc.infrastructure.eventbus import get_global_bus

                bus = get_global_bus()
            except Exception:
                return None
        return getattr(bus, "_redis", None)

    def _key(self, conversation_id: str) -> str:
        return f"{_KEY_PREFIX}{conversation_id}"

    async def get(self, conversation_id: str) -> str | None:
        """取已注册的 sandbox_id (跨 worker)。"""
        redis = self._redis
        if redis is not None:
            try:
                sid = await redis.get(self._key(conversation_id))
                return sid if sid else None
            except Exception as exc:
                logger.debug("SandboxRegistry redis get failed: %s", exc)
        return self._local.get(conversation_id)

    async def set(self, conversation_id: str, sandbox_id: str) -> None:
        """注册 sandbox_id (首个 worker create 后写入, 其他 worker 共享)。"""
        redis = self._redis
        if redis is not None:
            try:
                await redis.set(self._key(conversation_id), sandbox_id, ex=_TTL_SECONDS)
                return
            except Exception as exc:
                logger.debug("SandboxRegistry redis set failed: %s", exc)
        self._local[conversation_id] = sandbox_id

    async def remove(self, conversation_id: str) -> None:
        """注销 sandbox_id (沙箱销毁时)。"""
        redis = self._redis
        if redis is not None:
            try:
                await redis.delete(self._key(conversation_id))
                return
            except Exception:
                pass
        self._local.pop(conversation_id, None)


# 进程级单例 (惰性取全局 bus 的 Redis 连接)
sandbox_registry = SandboxRegistry()
