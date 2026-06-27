"""StorageAdapter.upload_dir + StaticSiteDeployer local filesystem 集成测试。

v6.10 TD-2: 从 test_deploy_service.py 迁出。原文件混合 StorageAdapter/Deployer/
类型路由注册点, 职责不清; 此处聚焦 infrastructure 层 local mode 部署链路。
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from arc.infrastructure.storage import StorageAdapter


@pytest.fixture
def local_adapter(monkeypatch):
    """Force local mode by clearing storage_endpoint."""
    monkeypatch.setattr("arc.config.settings.storage_endpoint", "")
    monkeypatch.setattr("arc.config.settings.storage_public_url", "")
    # Reset singleton
    import arc.infrastructure.storage as mod
    mod._adapter = None
    adapter = StorageAdapter()
    yield adapter
    mod._adapter = None


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """Create a fake dist directory."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>Hello</body></html>")
    (dist / "assets").mkdir()
    (dist / "assets" / "main.js").write_text("console.log('hi')")
    (dist / "assets" / "style.css").write_text("body{color:red}")
    return dist


class TestUploadDir:
    def test_uploads_all_files(self, local_adapter: StorageAdapter, dist_dir: Path) -> None:
        count = local_adapter.upload_dir(str(dist_dir), "test/prefix")
        assert count == 3

    def test_preserves_structure(self, local_adapter: StorageAdapter, dist_dir: Path) -> None:
        local_adapter.upload_dir(str(dist_dir), "deploy/abc")
        # Verify files exist in expected paths
        content = local_adapter.download("deploy/abc/index.html")
        assert content is not None
        assert b"Hello" in content

        content = local_adapter.download("deploy/abc/assets/main.js")
        assert content is not None
        assert b"console.log" in content

    def test_raises_on_nonexistent_dir(self, local_adapter: StorageAdapter) -> None:
        with pytest.raises(ValueError, match="目录不存在"):
            local_adapter.upload_dir("/nonexistent/path", "prefix")

    def test_raises_on_oversized_file(
        self, local_adapter: StorageAdapter, dist_dir: Path
    ) -> None:
        # Create a file that exceeds a tiny limit
        (dist_dir / "big.bin").write_bytes(b"x" * 100)
        with pytest.raises(ValueError, match="超过大小限制"):
            local_adapter.upload_dir(str(dist_dir), "prefix", max_file_size=50)


class TestStaticSiteDeployer:
    @pytest.mark.asyncio
    async def test_deploy_success(self, monkeypatch, dist_dir: Path) -> None:
        monkeypatch.setattr("arc.config.settings.storage_endpoint", "")
        monkeypatch.setattr("arc.config.settings.storage_public_url", "")
        import arc.infrastructure.storage as mod
        mod._adapter = None

        from arc.infrastructure.deployer.static_site import StaticSiteDeployer

        deployer = StaticSiteDeployer()
        result = await deployer.deploy(
            local_dir=str(dist_dir),
            project_id=uuid.uuid4(),
            deploy_id=uuid.uuid4(),
        )
        assert result.success is True
        assert "index.html" in result.url
        assert result.file_count == 3
        mod._adapter = None

    @pytest.mark.asyncio
    async def test_deploy_missing_dir(self, monkeypatch) -> None:
        monkeypatch.setattr("arc.config.settings.storage_endpoint", "")
        import arc.infrastructure.storage as mod
        mod._adapter = None

        from arc.infrastructure.deployer.static_site import StaticSiteDeployer

        deployer = StaticSiteDeployer()
        result = await deployer.deploy(
            local_dir="/nonexistent",
            project_id=uuid.uuid4(),
            deploy_id=uuid.uuid4(),
        )
        assert result.success is False
        assert "不存在" in result.error
        mod._adapter = None

    @pytest.mark.asyncio
    async def test_deploy_missing_index(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr("arc.config.settings.storage_endpoint", "")
        import arc.infrastructure.storage as mod
        mod._adapter = None

        # Dir exists but no index.html
        empty_dist = tmp_path / "empty"
        empty_dist.mkdir()
        (empty_dist / "app.js").write_text("// no index")

        from arc.infrastructure.deployer.static_site import StaticSiteDeployer

        deployer = StaticSiteDeployer()
        result = await deployer.deploy(
            local_dir=str(empty_dist),
            project_id=uuid.uuid4(),
            deploy_id=uuid.uuid4(),
        )
        assert result.success is False
        assert "index.html" in result.error
        mod._adapter = None
