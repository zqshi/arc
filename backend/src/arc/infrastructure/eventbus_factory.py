"""EventBus backend selection."""

from __future__ import annotations

from arc.infrastructure.eventbus import InMemoryEventBus
from arc.infrastructure.eventbus_contract import EventBus


def create_eventbus() -> EventBus:
    """按配置选择后端: redis_url 非空 → RedisEventBus, 否则 InMemory."""
    from arc.config import settings

    if settings.redis_url:
        from arc.infrastructure.redis_bus import RedisEventBus

        return RedisEventBus(settings.redis_url)
    return InMemoryEventBus()

