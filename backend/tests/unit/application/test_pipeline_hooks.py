"""Tests for pipeline hooks — _resolve_build_status 双读兼容 (v6.9 ④核心)。

验证 build_status 解析 fallback 链 (hooks.py:146):
BUILD artifact → build_evidence → app_code/prototype artifact → deploy_content.build_status

设计意图: BINARY_APP 构建链路产出 BUILD artifact (优先读), STATIC_SITE 无 BUILD 走
prototype content (fallback)。双读兼容存量无 BUILD 的部署报告。graceful: ArtifactRepository
异常 → fallback deploy_content.build_status 不阻断部署门禁。
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from arc.application.pipeline import hooks
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType


def _art(atype: ArtifactType, build_status: str | None = None) -> Artifact:
    """构造测试用 artifact — build_status=None 时 content 无该键 (模拟无构建状态)。"""
    content = {"build_status": build_status} if build_status else {}
    return Artifact(todo_id=uuid.uuid4(), artifact_type=atype, content=content)


class TestResolveBuildStatus:
    """_resolve_build_status 双读 fallback 链 (v6.9 ④核心)。"""

    @pytest.mark.asyncio
    async def test_build_artifact_wins_over_prototype(self):
        """BINARY_APP 主路径: BUILD artifact.build_status 优先于 prototype。"""
        arts = [_art(ArtifactType.BUILD, "success"), _art(ArtifactType.PROTOTYPE, "failed")]
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=arts)
            result = await hooks._resolve_build_status(AsyncMock(), uuid.uuid4(), {})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_build_artifact_with_empty_status_falls_through(self):
        """边界: BUILD 存在但 build_status 为空 → 跳过 BUILD 走后续 fallback。"""
        arts = [_art(ArtifactType.BUILD, None), _art(ArtifactType.PROTOTYPE, "success")]
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=arts)
            result = await hooks._resolve_build_status(AsyncMock(), uuid.uuid4(), {})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_build_evidence_fallback_when_no_build(self):
        """无 BUILD → deploy_content.build_evidence.build_status (deploy_report 旧链路)。"""
        arts = [_art(ArtifactType.PROTOTYPE, "failed")]
        deploy_content = {"build_evidence": {"build_status": "success"}}
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=arts)
            result = await hooks._resolve_build_status(
                AsyncMock(), uuid.uuid4(), deploy_content
            )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_prototype_fallback_when_no_build_no_evidence(self):
        """STATIC_SITE 主路径: 无 BUILD 无 evidence → prototype content.build_status。"""
        arts = [_art(ArtifactType.PROTOTYPE, "success")]
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=arts)
            result = await hooks._resolve_build_status(AsyncMock(), uuid.uuid4(), {})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_app_code_fallback_before_prototype(self):
        """fallback 顺序: app_code 优先于 prototype (按 APP_CODE/PROTOTYPE 迭代序)。"""
        arts = [_art(ArtifactType.APP_CODE, "success"), _art(ArtifactType.PROTOTYPE, "failed")]
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=arts)
            result = await hooks._resolve_build_status(AsyncMock(), uuid.uuid4(), {})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_deploy_content_fallback_when_no_artifacts(self):
        """全无 artifact/evidence → deploy_content.build_status (最后兜底)。"""
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(return_value=[])
            result = await hooks._resolve_build_status(
                AsyncMock(), uuid.uuid4(), {"build_status": "pending"}
            )
        assert result == "pending"

    @pytest.mark.asyncio
    async def test_graceful_on_repo_exception(self):
        """ArtifactRepository 异常 → fallback deploy_content.build_status 不阻断 (graceful)。"""
        with patch("arc.infrastructure.repositories.artifact.ArtifactRepository") as repo:
            repo.return_value.list_by_todo_id = AsyncMock(side_effect=RuntimeError("db down"))
            result = await hooks._resolve_build_status(
                AsyncMock(), uuid.uuid4(), {"build_status": "unknown"}
            )
        assert result == "unknown"
