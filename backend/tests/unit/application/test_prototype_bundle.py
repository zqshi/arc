"""PrototypeBundleService 单元测试 — 工程模式。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from arc.application.artifact.prototype_bundle import (
    PrototypeBundle,
    PrototypeBundleService,
)

# -- Fake domain objects for mocking ------------------------------------------


@dataclass
class FakeArtifact:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    todo_id: uuid.UUID | None = None
    content: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# -- Helpers ------------------------------------------------------------------


def _make_service() -> tuple[PrototypeBundleService, MagicMock]:
    """构造 service 并返回 mock 的 artifact_repo。"""
    svc = PrototypeBundleService.__new__(PrototypeBundleService)
    svc._db = MagicMock()
    svc._artifact_repo = MagicMock()
    return svc, svc._artifact_repo


# -- Tests: build_bundle (engineering mode) -----------------------------------


class TestBuildBundleEmpty:
    async def test_returns_empty_bundle_when_no_artifacts(self) -> None:
        svc, art_repo = _make_service()
        art_repo.list_by_project_and_type = AsyncMock(return_value=[])

        bundle = await svc.build_bundle(uuid.uuid4())

        assert isinstance(bundle, PrototypeBundle)
        assert bundle.preview_url == ""
        assert bundle.total_pages == 0
        assert bundle.routes == []


class TestBuildBundleEngineering:
    async def test_engineering_artifact_returns_preview_url(self) -> None:
        svc, art_repo = _make_service()
        project_id = uuid.uuid4()

        artifact = FakeArtifact(
            content={
                "project_dir": "prototype",
                "tech_stack": "vite-react-tailwind",
                "routes": [
                    {"path": "/", "name": "首页", "component": "src/pages/Home.tsx"},
                    {"path": "/login", "name": "登录", "component": "src/pages/Login.tsx"},
                ],
                "build_status": "success",
                "preview_url": "https://cdn.example.com/deployments/xxx/index.html",
            },
        )
        art_repo.list_by_project_and_type = AsyncMock(return_value=[artifact])

        bundle = await svc.build_bundle(project_id)

        assert bundle.preview_url == "https://cdn.example.com/deployments/xxx/index.html"
        assert bundle.total_pages == 2
        assert bundle.tech_stack == "vite-react-tailwind"
        assert bundle.routes[0].path == "/"
        assert bundle.routes[0].name == "首页"
        assert bundle.routes[1].path == "/login"

    async def test_latest_artifact_wins(self) -> None:
        """多个 prototype artifact 时，取最新的。"""
        svc, art_repo = _make_service()

        old_art = FakeArtifact(
            content={
                "project_dir": "prototype",
                "routes": [{"path": "/", "name": "旧首页", "component": ""}],
                "preview_url": "https://old.example.com/index.html",
            },
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        new_art = FakeArtifact(
            content={
                "project_dir": "prototype",
                "routes": [
                    {"path": "/", "name": "新首页", "component": ""},
                    {"path": "/about", "name": "关于", "component": ""},
                ],
                "preview_url": "https://new.example.com/index.html",
            },
            created_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        art_repo.list_by_project_and_type = AsyncMock(return_value=[old_art, new_art])

        bundle = await svc.build_bundle(uuid.uuid4())

        assert bundle.preview_url == "https://new.example.com/index.html"
        assert bundle.total_pages == 2
        assert bundle.routes[0].name == "新首页"

    async def test_no_preview_url_returns_empty_bundle(self) -> None:
        """有 project_dir 但没有 preview_url（尚未部署）。"""
        svc, art_repo = _make_service()

        artifact = FakeArtifact(
            content={
                "project_dir": "prototype",
                "build_status": "success",
                "routes": [{"path": "/", "name": "首页", "component": ""}],
            },
        )
        art_repo.list_by_project_and_type = AsyncMock(return_value=[artifact])

        bundle = await svc.build_bundle(uuid.uuid4())

        # 有路由信息但无预览 URL
        assert bundle.preview_url == ""
        assert bundle.total_pages == 1
        assert bundle.build_status == "success"

    async def test_version_id_uses_version_query(self) -> None:
        svc, art_repo = _make_service()
        version_id = uuid.uuid4()

        art_repo.list_by_version_and_type = AsyncMock(return_value=[])

        bundle = await svc.build_bundle(uuid.uuid4(), version_id=version_id)

        art_repo.list_by_version_and_type.assert_awaited_once()
        art_repo.list_by_project_and_type.assert_not_called()
        assert bundle.total_pages == 0

    async def test_non_engineering_artifact_returns_empty(self) -> None:
        """没有 project_dir 的旧格式 artifact 被忽略。"""
        svc, art_repo = _make_service()

        artifact = FakeArtifact(
            content={
                "pages": [{"name": "首页", "html": "<div>旧格式</div>"}],
            },
        )
        art_repo.list_by_project_and_type = AsyncMock(return_value=[artifact])

        bundle = await svc.build_bundle(uuid.uuid4())

        assert bundle.preview_url == ""
        assert bundle.total_pages == 0
