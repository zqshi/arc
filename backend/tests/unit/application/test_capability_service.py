"""CapabilityService 单元测试 (v6.8.0 W3 — 补 W1.3 遗留)。

mock repo 验证 service 纯逻辑: list_by_ids 透传 + create 同名冲突。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from arc.application.capability.service import CapabilityService
from arc.domain.capability.value_objects import (
    Capability,
    CapabilityType,
)
from arc.domain.errors import ConflictError


def _cap(name: str = "c1", type: CapabilityType = CapabilityType.AGENT) -> Capability:
    return Capability(id=uuid.uuid4(), name=name, type=type)


def _make_service() -> CapabilityService:
    """构造 service 并替换 repo 为 AsyncMock (隔离 DB)。"""
    svc = CapabilityService(db=AsyncMock())
    svc.repo = AsyncMock()
    return svc


class TestCapabilityServiceListByIds:
    @pytest.mark.asyncio
    async def test_list_by_ids_delegates_to_repo(self) -> None:
        svc = _make_service()
        caps = [_cap("c1"), _cap("c2")]
        svc.repo.list_by_ids.return_value = caps
        ids = [c.id for c in caps]

        result = await svc.list_by_ids(ids)

        svc.repo.list_by_ids.assert_awaited_once_with(ids)
        assert result == caps

    @pytest.mark.asyncio
    async def test_list_by_ids_empty_returns_empty(self) -> None:
        svc = _make_service()
        svc.repo.list_by_ids.return_value = []

        assert await svc.list_by_ids([]) == []
        svc.repo.list_by_ids.assert_awaited_once_with([])


class TestCapabilityServiceCreate:
    @pytest.mark.asyncio
    async def test_create_raises_on_name_conflict(self) -> None:
        svc = _make_service()
        svc.repo.get_by_name.return_value = _cap("existing")

        with pytest.raises(ConflictError):
            await svc.create(
                name="dup", type="agent", config={}, status="active", scope="global"
            )
        svc.repo.create.assert_not_awaited()
