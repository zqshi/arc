"""项目宪章 (project_charter) 集成测试 (v6.3.0 T1)。

验证 charter 贯穿: 创建时自动产出 → DB 持久化 → 响应返回, 且骨架意图驱动 (无硬规则)。
与 conventions 并存: charter 系统生成, conventions 用户补充。
端到端覆盖 T1(domain 值对象 + entity 方法) + workspace_service(产出) +
infrastructure(ORM/migration/repo) + interface(schema/响应)。
"""
from __future__ import annotations

from httpx import AsyncClient


class TestProjectCharter:
    async def test_create_has_charter(self, client: AsyncClient):
        """创建项目 → 响应含 charter (系统自动产出, 非空)。"""
        resp = await client.post("/api/projects", json={"name": "Charter Has"})
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert body["charter"] is not None
        assert body["charter"]["markdown"]
        assert body["charter"]["template_version"] == 1

    async def test_charter_project_type_defaults_static_site(self, client: AsyncClient):
        """默认 project_type=static_site → charter.project_type 匹配。"""
        resp = await client.post("/api/projects", json={"name": "Charter Default"})
        assert resp.json()["charter"]["project_type"] == "static_site"

    async def test_charter_persists_across_requests(self, client: AsyncClient):
        """GET 重查验证 DB 持久化, 排除内存默认值假象。"""
        create = await client.post("/api/projects", json={"name": "Charter Persist"})
        pid = create.json()["id"]

        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        charter = resp.json()["charter"]
        assert charter is not None
        assert charter["markdown"]
        assert charter["project_type"] == "static_site"

    async def test_create_binary_app_charter(self, client: AsyncClient):
        """binary_app 项目 → charter.project_type == binary_app (T1 通用骨架, 内容 T2 才特化)。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "Charter Binary", "project_type": "binary_app"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["charter"]["project_type"] == "binary_app"

    async def test_charter_markdown_is_intent_driven(self, client: AsyncClient):
        """端到端验证: 产出的 charter 骨架禁用规则执行式硬规则 (意图驱动约束)。"""
        resp = await client.post("/api/projects", json={"name": "Charter Intent"})
        md = resp.json()["charter"]["markdown"]
        forbidden = [
            "500 行", "500行", "< 500", "800 行", "800行",
            "单文件行数上限", "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项",
        ]
        for token in forbidden:
            assert token not in md, f"charter 含硬规则措辞: {token!r}"
        # 含意图驱动结构标记
        assert "目标" in md
        assert "输出契约" in md

    async def test_charter_coexists_with_conventions(self, client: AsyncClient):
        """charter (系统生成) 与 conventions (用户补充) 并存, 互不覆盖。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "Charter Coexist", "conventions": "用户自定义约定"},
        )
        body = resp.json()
        assert body["charter"] is not None  # 系统生成
        assert body["conventions"] == "用户自定义约定"  # 用户补充保留

    async def test_charter_not_editable_on_create(self, client: AsyncClient):
        """ProjectCreate 不接受 charter 字段 (创建时系统生成, 编辑留 T3)。
        传入应被 pydantic 忽略 (extra 默认 ignore) 或不影响系统生成。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "Charter NoInput", "charter": {"markdown": "注入"}},
        )
        assert resp.status_code in (200, 201)
        # 系统生成覆盖任何用户输入 (charter 来自 provider, 非用户)
        assert resp.json()["charter"]["markdown"] != "注入"
