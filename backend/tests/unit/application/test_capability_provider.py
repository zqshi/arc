"""CapabilityProvider 单元测试 (v6.8.0 W3.2).

mock ProjectRepository / CapabilityService, 真实 SkillLoader (tmp_path SKILL.md)。
覆盖: 无配置/项目不存在→空, skill 注入, skill 文件缺失→skip, agent 提示, 全禁用→空。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.context.providers.capability import CapabilityProvider
from arc.application.context.protocol import ContextRequest
from arc.domain.capability.value_objects import (
    Capability,
    CapabilityStatus,
    CapabilityType,
)
from arc.domain.project.entity import Project

_PROJ_REPO = "arc.infrastructure.repositories.project.ProjectRepository"
_CAP_SVC = "arc.application.capability.service.CapabilityService"


def _cap(name, type, status=CapabilityStatus.ACTIVE, config=None):
    return Capability(
        id=uuid.uuid4(), name=name, type=type, status=status, config=config or {}
    )


def _request(phase="development", project_id=None):
    return ContextRequest(
        todo=MagicMock(),
        conversation=MagicMock(),
        phase=phase,
        project_id=project_id or uuid.uuid4(),
    )


def _project(phase_caps=None):
    p = Project(name="p")
    if phase_caps:
        p.pipeline_config["phase_capabilities"] = phase_caps
    return p


class TestCapabilityProvider:
    @pytest.mark.asyncio
    async def test_no_project_id_returns_empty(self) -> None:
        provider = CapabilityProvider(db=MagicMock())
        request = ContextRequest(
            todo=MagicMock(), conversation=MagicMock(),
            phase="development", project_id=None,
        )
        assert await provider.provide(request) == []

    @pytest.mark.asyncio
    async def test_project_not_found_returns_empty(self) -> None:
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=None)
            assert await provider.provide(_request()) == []

    @pytest.mark.asyncio
    async def test_phase_without_config_returns_empty(self) -> None:
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=_project())
            assert await provider.provide(_request(phase="testing")) == []

    @pytest.mark.asyncio
    async def test_skill_injection(self, tmp_path) -> None:
        skill_dir = tmp_path / "ui-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ui-skill\ndescription: UI design skill\n---\nbody content here",
            encoding="utf-8",
        )
        cap = _cap("ui-skill", CapabilityType.SKILL, config={"directory": str(skill_dir)})
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo, patch(_CAP_SVC) as MockSvc:
            MockRepo.return_value.get_by_id = AsyncMock(
                return_value=_project({"development": [str(cap.id)]})
            )
            MockSvc.return_value.list_by_ids = AsyncMock(return_value=[cap])
            result = await provider.provide(_request(phase="development"))
        assert len(result) == 1
        assert result[0].source == "capability"
        assert "ui-skill" in result[0].content
        assert "body content here" in result[0].content

    @pytest.mark.asyncio
    async def test_skill_file_missing_skipped(self, tmp_path) -> None:
        cap = _cap(
            "missing", CapabilityType.SKILL, config={"directory": str(tmp_path / "nope")}
        )
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo, patch(_CAP_SVC) as MockSvc:
            MockRepo.return_value.get_by_id = AsyncMock(
                return_value=_project({"development": [str(cap.id)]})
            )
            MockSvc.return_value.list_by_ids = AsyncMock(return_value=[cap])
            assert await provider.provide(_request(phase="development")) == []

    @pytest.mark.asyncio
    async def test_agent_capability_hint(self) -> None:
        cap = _cap("openhands", CapabilityType.AGENT)
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo, patch(_CAP_SVC) as MockSvc:
            MockRepo.return_value.get_by_id = AsyncMock(
                return_value=_project({"development": [str(cap.id)]})
            )
            MockSvc.return_value.list_by_ids = AsyncMock(return_value=[cap])
            result = await provider.provide(_request(phase="development"))
        assert len(result) == 1
        assert "openhands" in result[0].content
        assert "agent" in result[0].content

    @pytest.mark.asyncio
    async def test_all_disabled_returns_empty(self) -> None:
        cap = _cap("dis", CapabilityType.SKILL, status=CapabilityStatus.DISABLED)
        provider = CapabilityProvider(db=MagicMock())
        with patch(_PROJ_REPO) as MockRepo, patch(_CAP_SVC) as MockSvc:
            MockRepo.return_value.get_by_id = AsyncMock(
                return_value=_project({"development": [str(cap.id)]})
            )
            MockSvc.return_value.list_by_ids = AsyncMock(return_value=[cap])
            assert await provider.provide(_request(phase="development")) == []
