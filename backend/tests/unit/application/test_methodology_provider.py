"""Tests for MethodologyProvider — v5.9.0 按 project_type 注入原型工程指导。

覆盖 providers/methodology.py._build 的注入分支:
- ui_design/development + prototype 未完成 + project 存在 → 注入 get_prototype_guide
- prototype 已完成 / project 不存在 / 非原型阶段 → 不注入
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from arc.application.context.providers.methodology import MethodologyProvider
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType


def _make_request(phase: str = "ui_design", completed: list[str] | None = None) -> SimpleNamespace:
    """轻量构造 ContextRequest (duck typing, _build 只访问这几个属性)。"""
    return SimpleNamespace(
        todo=SimpleNamespace(project_id=uuid.uuid4()),
        conversation=SimpleNamespace(messages=[]),
        phase=phase,
        completed_artifacts=completed if completed is not None else [],
    )


class TestMethodologyPrototypeGuideInjection:
    """v5.9.0: methodology provider 按 project_type 注入原型工程指导。"""

    @pytest.mark.asyncio
    async def test_injects_guide_for_static_site_in_ui_design(self):
        project = Project(name="t", project_type=ProjectType.STATIC_SITE)
        request = _make_request(phase="ui_design")
        with patch("arc.infrastructure.repositories.project.ProjectRepository") as MockRepo, \
             patch(
                 "arc.application.execution.constraint_policy.get_methodology_prompt_for_constraint",
                 return_value="METHODOLOGY-BASE",
             ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=project)
            provider = MethodologyProvider(db=AsyncMock())
            result = await provider._build(request)
        assert "METHODOLOGY-BASE" in result
        assert "原型工程要求" in result  # PROTOTYPE_ENGINEERING_PROMPT 关键文案

    @pytest.mark.asyncio
    async def test_injects_guide_in_development(self):
        project = Project(name="t", project_type=ProjectType.STATIC_SITE)
        request = _make_request(phase="development")
        with patch("arc.infrastructure.repositories.project.ProjectRepository") as MockRepo, \
             patch(
                 "arc.application.execution.constraint_policy.get_methodology_prompt_for_constraint",
                 return_value="METHODOLOGY-BASE",
             ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=project)
            provider = MethodologyProvider(db=AsyncMock())
            result = await provider._build(request)
        assert "原型工程要求" in result

    @pytest.mark.asyncio
    async def test_skips_when_prototype_completed(self):
        project = Project(name="t", project_type=ProjectType.STATIC_SITE)
        request = _make_request(phase="ui_design", completed=["prototype"])
        with patch("arc.infrastructure.repositories.project.ProjectRepository") as MockRepo, \
             patch(
                 "arc.application.execution.constraint_policy.get_methodology_prompt_for_constraint",
                 return_value="METHODOLOGY-BASE",
             ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=project)
            provider = MethodologyProvider(db=AsyncMock())
            result = await provider._build(request)
        assert "原型工程要求" not in result

    @pytest.mark.asyncio
    async def test_skips_when_no_project(self):
        request = _make_request(phase="ui_design")
        with patch("arc.infrastructure.repositories.project.ProjectRepository") as MockRepo, \
             patch(
                 "arc.application.execution.constraint_policy.get_methodology_prompt_for_constraint",
                 return_value="METHODOLOGY-BASE",
             ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=None)
            provider = MethodologyProvider(db=AsyncMock())
            result = await provider._build(request)
        assert "原型工程要求" not in result

    @pytest.mark.asyncio
    async def test_skips_in_non_prototype_phase(self):
        project = Project(name="t", project_type=ProjectType.STATIC_SITE)
        request = _make_request(phase="architecture")
        with patch("arc.infrastructure.repositories.project.ProjectRepository") as MockRepo, \
             patch(
                 "arc.application.execution.constraint_policy.get_methodology_prompt_for_constraint",
                 return_value="METHODOLOGY-BASE",
             ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=project)
            provider = MethodologyProvider(db=AsyncMock())
            result = await provider._build(request)
        assert "原型工程要求" not in result
