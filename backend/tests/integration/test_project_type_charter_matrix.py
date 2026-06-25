"""不同 ProjectType 生成不同规范 — 端到端验证矩阵 (v6.3.0 T4)。

验证类型差异贯穿三层: charter(DB JSONB) → CHARTER.md(落盘) → CLAUDE.md(落盘)。
补齐 T2(charter DB 类型差异) 与 T3(落盘) 之间的端到端贯通验证。

矩阵断言: static_site vs binary_app 创建后, 三处都正确反映类型特化,
特化段落互斥, 通用治理骨架共享, 全程意图驱动无硬规则。
"""
from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient


class TestProjectTypeCharterMatrix:
    """类型差异端到端矩阵: DB charter + 落盘 CHARTER.md + 落盘 CLAUDE.md。"""

    async def _create_and_collect(self, client: AsyncClient, name: str, ptype: str):
        resp = await client.post(
            "/api/projects", json={"name": name, "project_type": ptype}
        )
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        local_path = body["local_path"]
        return {
            "db_charter_md": body["charter"]["markdown"],
            "db_project_type": body["charter"]["project_type"],
            "charter_file": (
                Path(local_path) / ".arc" / "governance" / "CHARTER.md"
            ).read_text(encoding="utf-8"),
            "context_file": (Path(local_path) / "CLAUDE.md").read_text(encoding="utf-8"),
        }

    async def test_static_site_full_chain(self, client: AsyncClient):
        """static_site: DB charter + CHARTER.md + CLAUDE.md 都含静态站点特化。"""
        data = await self._create_and_collect(client, "Matrix Static", "static_site")

        assert data["db_project_type"] == "static_site"
        # DB charter
        assert "静态站点特化治理意图" in data["db_charter_md"]
        assert "可发现性意图" in data["db_charter_md"]  # SEO
        # 落盘 CHARTER.md == DB charter
        assert data["charter_file"] == data["db_charter_md"]
        # 落盘 CHARTER.md 也含特化
        assert "静态站点特化治理意图" in data["charter_file"]

    async def test_binary_app_full_chain(self, client: AsyncClient):
        """binary_app: DB charter + CHARTER.md 都含客户端特化。"""
        data = await self._create_and_collect(client, "Matrix Binary", "binary_app")

        assert data["db_project_type"] == "binary_app"
        assert "原生客户端特化治理意图" in data["db_charter_md"]
        assert "可信分发意图" in data["db_charter_md"]  # 签名
        assert data["charter_file"] == data["db_charter_md"]
        assert "原生客户端特化治理意图" in data["charter_file"]

    async def test_specialization_mutually_exclusive(self, client: AsyncClient):
        """特化段落互斥: static_site 不含客户端特化, binary_app 不含站点特化。"""
        static = await self._create_and_collect(client, "Mutex Static", "static_site")
        binary = await self._create_and_collect(client, "Mutex Binary", "binary_app")

        # DB 层互斥
        assert "静态站点特化治理意图" in static["db_charter_md"]
        assert "静态站点特化治理意图" not in binary["db_charter_md"]
        assert "原生客户端特化治理意图" in binary["db_charter_md"]
        assert "原生客户端特化治理意图" not in static["db_charter_md"]

        # 落盘 CHARTER.md 层互斥 (落盘未丢失/串类型)
        assert "静态站点特化治理意图" in static["charter_file"]
        assert "静态站点特化治理意图" not in binary["charter_file"]
        assert "原生客户端特化治理意图" in binary["charter_file"]
        assert "原生客户端特化治理意图" not in static["charter_file"]

    async def test_common_skeleton_shared_across_types(self, client: AsyncClient):
        """通用治理骨架 (4 样机制意图) 两种类型都共享, 不因特化丢失。"""
        static = await self._create_and_collect(client, "Shared Static", "static_site")
        binary = await self._create_and_collect(client, "Shared Binary", "binary_app")

        common_markers = [
            "上下文加载意图",
            "版本迭代意图",
            "代码规范意图",
            "质量守护意图",
            "规范维护意图",
        ]
        for marker in common_markers:
            assert marker in static["db_charter_md"], f"static_site 缺通用段: {marker}"
            assert marker in binary["db_charter_md"], f"binary_app 缺通用段: {marker}"

    async def test_all_artifacts_intent_driven_no_hard_rules(self, client: AsyncClient):
        """全程意图驱动: DB charter + CHARTER.md + CLAUDE.md 都禁硬规则措辞。"""
        forbidden = [
            "500 行", "500行", "800 行", "单文件行数上限",
            "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项",
        ]
        for ptype in ("static_site", "binary_app"):
            data = await self._create_and_collect(
                client, f"NoRules {ptype}", ptype
            )
            for token in forbidden:
                assert token not in data["db_charter_md"], (
                    f"{ptype} DB charter 含硬规则: {token!r}"
                )
                assert token not in data["charter_file"], (
                    f"{ptype} CHARTER.md 含硬规则: {token!r}"
                )
                assert token not in data["context_file"], (
                    f"{ptype} CLAUDE.md 含硬规则: {token!r}"
                )

    async def test_context_md_same_common_intents_across_types(self, client: AsyncClient):
        """CLAUDE.md (操作投影) 两种类型都含 4 样机制操作意图段。"""
        static = await self._create_and_collect(client, "Ctx Static", "static_site")
        binary = await self._create_and_collect(client, "Ctx Binary", "binary_app")

        for marker in ("上下文加载意图", "版本迭代意图", "任务编排意图", "质量守护意图"):
            assert marker in static["context_file"]
            assert marker in binary["context_file"]

    async def test_default_type_is_static_site(self, client: AsyncClient):
        """不传 project_type → 默认 static_site, 生成 static_site charter。"""
        resp = await client.post("/api/projects", json={"name": "Matrix Default"})
        body = resp.json()
        assert body["project_type"] == "static_site"
        assert body["charter"]["project_type"] == "static_site"
        assert "静态站点特化治理意图" in body["charter"]["markdown"]
