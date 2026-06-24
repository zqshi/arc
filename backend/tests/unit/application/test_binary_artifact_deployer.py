"""BinaryArtifactDeployer 单元测试 — v6.0 T5。

验证二进制制品部署器: 产物落制品目录(不分发, 不要求 index.html)。
复用 storage 抽象, local storage 模式(与 TestStaticSiteDeployer 同)。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest


def _local_storage(monkeypatch):
    """强制 local storage 模式并重置单例。"""
    monkeypatch.setattr("arc.config.settings.storage_endpoint", "")
    monkeypatch.setattr("arc.config.settings.storage_public_url", "")
    import arc.infrastructure.storage as mod
    mod._adapter = None
    return mod


@pytest.fixture
def binary_dist(tmp_path: Path) -> Path:
    """模拟 Tauri 构建产物目录(含二进制文件, 无 index.html)。"""
    dist = tmp_path / "bundle"
    dist.mkdir()
    (dist / "myapp").write_bytes(b"\x7fELF binary content")  # linux 二进制
    (dist / "myapp.apk").write_bytes(b"PK apk content")  # android
    return dist


class TestBinaryArtifactDeployer:
    @pytest.mark.asyncio
    async def test_deploy_success(self, monkeypatch, binary_dist: Path) -> None:
        mod = _local_storage(monkeypatch)
        try:
            from arc.infrastructure.deployer.binary_artifact import (
                BinaryArtifactDeployer,
            )

            deployer = BinaryArtifactDeployer()
            result = await deployer.deploy(
                local_dir=str(binary_dist),
                project_id=uuid.uuid4(),
                deploy_id=uuid.uuid4(),
            )
            assert result.success is True
            assert result.file_count == 2
            # 制品根路径, 不指向 index.html
            assert "artifacts" in result.prefix
            assert "index.html" not in result.url
        finally:
            mod._adapter = None

    @pytest.mark.asyncio
    async def test_deploy_missing_dir(self, monkeypatch) -> None:
        mod = _local_storage(monkeypatch)
        try:
            from arc.infrastructure.deployer.binary_artifact import (
                BinaryArtifactDeployer,
            )

            deployer = BinaryArtifactDeployer()
            result = await deployer.deploy(
                local_dir="/nonexistent",
                project_id=uuid.uuid4(),
                deploy_id=uuid.uuid4(),
            )
            assert result.success is False
            assert "不存在" in result.error
        finally:
            mod._adapter = None

    @pytest.mark.asyncio
    async def test_deploy_empty_dir_fails(self, monkeypatch, tmp_path: Path) -> None:
        """空产物目录应失败(无制品可部署)。"""
        mod = _local_storage(monkeypatch)
        try:
            from arc.infrastructure.deployer.binary_artifact import (
                BinaryArtifactDeployer,
            )

            empty = tmp_path / "empty"
            empty.mkdir()
            deployer = BinaryArtifactDeployer()
            result = await deployer.deploy(
                local_dir=str(empty),
                project_id=uuid.uuid4(),
                deploy_id=uuid.uuid4(),
            )
            assert result.success is False
            assert "无构建产物" in result.error or "空" in result.error
        finally:
            mod._adapter = None

    @pytest.mark.asyncio
    async def test_deploy_does_not_require_index_html(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """与 StaticSiteDeployer 关键差异: 不要求 index.html, 有二进制即可。"""
        mod = _local_storage(monkeypatch)
        try:
            from arc.infrastructure.deployer.binary_artifact import (
                BinaryArtifactDeployer,
            )

            dist = tmp_path / "bundle"
            dist.mkdir()
            # 只有二进制, 无 index.html — StaticSite 会失败, Binary 应成功
            (dist / "app").write_bytes(b"\x7fELF")
            deployer = BinaryArtifactDeployer()
            result = await deployer.deploy(
                local_dir=str(dist),
                project_id=uuid.uuid4(),
                deploy_id=uuid.uuid4(),
            )
            assert result.success is True
        finally:
            mod._adapter = None
