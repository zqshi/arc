"""B5 投产门禁: RateLimitMiddleware Redis 后端单测。

_check_memory (内存滑动窗口) + _check_redis (Redis sorted set 滑动窗口, 多副本共享)。
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from arc.interface.middleware.rate_limit import RateLimitMiddleware


def _make_middleware(redis: bool = False) -> RateLimitMiddleware:
    m = RateLimitMiddleware(MagicMock())
    if redis:
        m._redis = AsyncMock()
    return m


class TestCheckMemory:
    async def test_under_limit_allows_until_limit(self):
        m = _make_middleware()
        now = time.time()
        assert m._check_memory("k", now, 3) is True
        assert m._check_memory("k", now, 3) is True
        assert m._check_memory("k", now, 3) is True  # 3rd — 达上限
        assert m._check_memory("k", now, 3) is False  # 4th 被限流

    async def test_window_expiry_allows_again(self):
        m = _make_middleware()
        now = time.time()
        for _ in range(3):
            m._check_memory("k", now, 3)
        # 窗口过期后重新允许
        assert m._check_memory("k", now + 61, 3) is True


class TestCheckRedis:
    async def test_under_limit_allows_and_zadd(self):
        m = _make_middleware(redis=True)
        m._redis.zremrangebyscore = AsyncMock()
        m._redis.zcard = AsyncMock(return_value=2)
        m._redis.zadd = AsyncMock()
        m._redis.expire = AsyncMock()
        allowed = await m._check_redis("k", time.time(), 3)
        assert allowed is True
        m._redis.zadd.assert_called_once()
        m._redis.expire.assert_called_once()

    async def test_at_limit_blocks_no_zadd(self):
        m = _make_middleware(redis=True)
        m._redis.zremrangebyscore = AsyncMock()
        m._redis.zcard = AsyncMock(return_value=3)
        m._redis.zadd = AsyncMock()
        m._redis.expire = AsyncMock()
        allowed = await m._check_redis("k", time.time(), 3)
        assert allowed is False
        m._redis.zadd.assert_not_called()  # 超限不写

    async def test_prunes_expired_before_count(self):
        """zremrangebyscore 在 zcard 前调用 (清窗口外)。"""
        m = _make_middleware(redis=True)
        m._redis.zremrangebyscore = AsyncMock()
        m._redis.zcard = AsyncMock(return_value=0)
        m._redis.zadd = AsyncMock()
        m._redis.expire = AsyncMock()
        await m._check_redis("k", time.time(), 3)
        m._redis.zremrangebyscore.assert_called_once()
