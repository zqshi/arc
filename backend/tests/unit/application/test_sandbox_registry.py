"""SandboxRegistry 测试 (v6.7 全量多 worker)。

验证 sandbox_id 跨 worker 共享: Redis 路径 (多 worker) + 进程内降级 (无 Redis)。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.sandbox.registry import SandboxRegistry


class TestSandboxRegistryInMemory:
    """无 Redis (单 worker) → 进程内 dict 降级。"""

    @pytest.mark.asyncio
    async def test_set_get_in_memory(self):
        reg = SandboxRegistry(bus=None)  # bus=None → _redis None → 进程内
        assert await reg.get("c1") is None
        await reg.set("c1", "sb-123")
        assert await reg.get("c1") == "sb-123"

    @pytest.mark.asyncio
    async def test_remove_in_memory(self):
        reg = SandboxRegistry(bus=None)
        await reg.set("c1", "sb-123")
        await reg.remove("c1")
        assert await reg.get("c1") is None


class TestSandboxRegistryRedis:
    """有 Redis (多 worker) → Redis 存取, 跨 worker 共享。"""

    @pytest.mark.asyncio
    async def test_set_get_redis(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="sb-456")
        mock_bus = MagicMock(_redis=mock_redis)
        reg = SandboxRegistry(bus=mock_bus)

        assert await reg.get("c1") == "sb-456"
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_writes_redis_with_ttl(self):
        mock_redis = AsyncMock()
        mock_bus = MagicMock(_redis=mock_redis)
        reg = SandboxRegistry(bus=mock_bus)

        await reg.set("c1", "sb-789")
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args
        assert args[0][0] == "arc:sandbox-id:c1"
        assert args[0][1] == "sb-789"
        assert "ex" in args.kwargs  # TTL

    @pytest.mark.asyncio
    async def test_redis_fallback_to_inmemory_on_error(self):
        """Redis 异常 → 降级进程内, 不阻断。"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("redis down"))
        mock_bus = MagicMock(_redis=mock_redis)
        reg = SandboxRegistry(bus=mock_bus)

        # get 异常 → 返回 None (不抛)
        assert await reg.get("c1") is None


class TestSandboxRegistryKey:
    def test_key_format(self):
        reg = SandboxRegistry(bus=None)
        assert reg._key("conv-1") == "arc:sandbox-id:conv-1"
