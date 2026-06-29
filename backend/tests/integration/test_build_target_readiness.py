"""构建目标就绪状态查询集成测试 (v6.19 T11 方案3)。

验证 GET /api/projects/build-targets 端点: 路由可达 (不被 /{project_id} 拦截)、
返回所有 BuildTarget 就绪状态、结构正确、就绪不变量 (ready↔reason)。
docker target 恒就绪 (不依赖凭证); CI target 状态据测试环境 settings。
"""
from __future__ import annotations

from httpx import AsyncClient


class TestBuildTargetReadiness:
    async def test_endpoint_reachable_not_shadowed_by_project_id(self, client: AsyncClient):
        """GET /build-targets 不被 core 的 GET /{project_id} 拦截 (路由顺序守护)。

        若被 /{project_id} 拦截, 返回 404 (project_id="build-targets" 不存在)。
        """
        resp = await client.get("/api/projects/build-targets")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_returns_all_six_targets(self, client: AsyncClient):
        """返回全部 6 个 BuildTarget (3 docker + 3 CI)。"""
        resp = await client.get("/api/projects/build-targets")
        targets = {item["target"] for item in resp.json()}
        assert targets == {
            "tauri_linux", "web", "capacitor_apk",
            "tauri_windows", "capacitor_ios", "harmony_hap",
        }

    async def test_response_shape(self, client: AsyncClient):
        """每项含 target/ready/reason 三字段且类型正确。"""
        resp = await client.get("/api/projects/build-targets")
        for item in resp.json():
            assert set(item.keys()) == {"target", "ready", "reason"}
            assert isinstance(item["target"], str)
            assert isinstance(item["ready"], bool)
            assert isinstance(item["reason"], str)

    async def test_docker_targets_always_ready(self, client: AsyncClient):
        """docker target 无外部依赖, 恒就绪 (不依赖 CI 凭证配置)。"""
        resp = await client.get("/api/projects/build-targets")
        by_target = {item["target"]: item for item in resp.json()}
        for t in ("tauri_linux", "web", "capacitor_apk"):
            assert by_target[t]["ready"] is True, t
            assert by_target[t]["reason"] == ""

    async def test_reason_empty_iff_ready(self, client: AsyncClient):
        """就绪不变量: ready=True→reason 空, ready=False→reason 非空 (前端灰显依据)。"""
        resp = await client.get("/api/projects/build-targets")
        for item in resp.json():
            if item["ready"]:
                assert item["reason"] == ""
            else:
                assert item["reason"] != ""
