"""治理产物落盘集成测试 (v6.3.0 T3)。

验证创建项目后 local_path 下交付治理文件存在 (CHARTER.md + CLAUDE.md),
内容正确, 以及 github 类型 clone 后补落盘。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from arc.application.integration.github_service import GitHubService
from arc.application.project.convention_templates import ConventionTemplateRegistry
from arc.application.project.governance_writer import GovernanceArtifactWriter
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType


class TestGovernanceArtifactsOnCreate:
    async def test_temporary_project_writes_governance_files(self, client: AsyncClient):
        """创建 temporary 项目 → local_path 下 CHARTER.md + CLAUDE.md 存在。"""
        resp = await client.post("/api/projects", json={"name": "Gov Artifacts"})
        assert resp.status_code in (200, 201)
        body = resp.json()
        local_path = body["local_path"]

        charter = Path(local_path) / ".arc" / "governance" / "CHARTER.md"
        context = Path(local_path) / "CLAUDE.md"
        assert charter.exists(), "CHARTER.md 应落盘"
        assert context.exists(), "CLAUDE.md 应落盘"

    async def test_charter_file_matches_db(self, client: AsyncClient):
        """落盘的 CHARTER.md 内容 == DB project.charter.markdown。"""
        resp = await client.post("/api/projects", json={"name": "Gov Match"})
        local_path = resp.json()["local_path"]

        charter_file = Path(local_path) / ".arc" / "governance" / "CHARTER.md"
        db_charter_md = resp.json()["charter"]["markdown"]
        assert charter_file.read_text(encoding="utf-8") == db_charter_md

    async def test_context_md_has_four_intents(self, client: AsyncClient):
        """CLAUDE.md 含 4 样机制操作意图段。"""
        resp = await client.post("/api/projects", json={"name": "Gov Intents"})
        ctx = (Path(resp.json()["local_path"]) / "CLAUDE.md").read_text(encoding="utf-8")

        assert "上下文加载意图" in ctx
        assert "版本迭代意图" in ctx
        assert "任务编排意图" in ctx
        assert "质量守护意图" in ctx

    async def test_context_md_no_hard_rules(self, client: AsyncClient):
        """CLAUDE.md 禁规则执行式硬规则。"""
        resp = await client.post("/api/projects", json={"name": "Gov NoRules"})
        ctx = (Path(resp.json()["local_path"]) / "CLAUDE.md").read_text(encoding="utf-8")

        forbidden = [
            "500 行", "500行", "800 行", "单文件行数上限",
            "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项",
        ]
        for token in forbidden:
            assert token not in ctx, f"CLAUDE.md 含硬规则: {token!r}"

    async def test_conventions_appear_in_context_md(self, client: AsyncClient):
        """用户 conventions 非空时注入 CLAUDE.md 项目特定治理段。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "Gov Conv", "conventions": "用户的特殊约定"},
        )
        ctx = (Path(resp.json()["local_path"]) / "CLAUDE.md").read_text(encoding="utf-8")
        assert "项目特定治理" in ctx
        assert "用户的特殊约定" in ctx

    async def test_artifacts_regenerated_on_reinit(self, client: AsyncClient, db_session):
        """charter 升级 (重新 initialize) 后落盘文件更新 (幂等覆盖)。"""
        from arc.infrastructure.repositories.project import ProjectRepository

        create = await client.post("/api/projects", json={"name": "Gov Reinit"})
        pid = create.json()["id"]
        local_path = create.json()["local_path"]
        charter_file = Path(local_path) / ".arc" / "governance" / "CHARTER.md"

        # 重新 initialize charter (模拟升级), 再落盘
        repo = ProjectRepository(db_session)
        project = await repo.get_by_id(pid)
        project.initialize_charter(ConventionTemplateRegistry())
        GovernanceArtifactWriter().write(project)

        updated = charter_file.read_text(encoding="utf-8")
        assert updated == project.charter.markdown  # 文件 == 新 charter


class TestGithubCloneBackfillsGovernance:
    async def test_governance_files_after_clone(self, db_session, tmp_path):
        """github 类型 clone 后 local_path 就绪, 补落治理产物。"""
        project = Project(
            name="github-proj",
            repo_url="https://github.com/acme/widget",
            local_path="",
            project_type=ProjectType.STATIC_SITE,
        )
        # clone 前 charter 已初始化 (create_project 时生成, local_path 空跳过落盘)
        project.initialize_charter(ConventionTemplateRegistry())
        assert project.charter is not None

        svc = GitHubService(db_session)
        svc.project_repo = AsyncMock()

        target = tmp_path / "cloned-repo"
        # patch asyncio.to_thread (跳过真实 git clone) + scan_manager
        with patch("arc.application.integration.github_service.asyncio") as mock_aio:
            mock_aio.to_thread = AsyncMock(return_value="cloned")
            with patch("arc.application.project.scan_task.scan_manager") as mock_scan:
                mock_scan.is_running.return_value = False
                mock_scan.start_scan = AsyncMock()
                await svc.clone_repo(project, str(target))

        # clone 后 local_path 就绪, 治理产物应已补落盘
        assert (target / "CLAUDE.md").exists()
        assert (target / ".arc" / "governance" / "CHARTER.md").exists()
        assert project.local_path == str(target)
