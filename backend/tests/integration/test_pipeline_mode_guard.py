"""v6.15 后端模式守卫集成测试。

验证 pipeline 写操作 (STRICT 专属) 在非严格模式下被拦截:
- FREE/MODERATE 模式的 todo 调 pipeline 写操作 → 409 mode_mismatch
- STRICT 模式 → 放行 (交由后续 phase/gate 逻辑)
- 读操作 (get_pipeline) 与 artifact 操作不守 (跨模式共享)

守卫真相源: todo.project_id → project.process_constraint;
无 project 的独立 todo 回退 todo.execution_mode (默认 PIPELINE→strict)。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def free_project(client: AsyncClient) -> str:
    """创建 FREE 模式 project, 返回 project_id。"""
    resp = await client.post("/api/projects", json={
        "name": "free-mode-project",
        "process_constraint": "free",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
async def strict_project(client: AsyncClient) -> str:
    """创建 STRICT 模式 project, 返回 project_id。"""
    resp = await client.post("/api/projects", json={
        "name": "strict-mode-project",
        "process_constraint": "strict",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_todo(client: AsyncClient, project_id: str | None) -> str:
    """创建 todo (可关联 project), 返回 todo_id。"""
    body = {"title": "guarded todo", "description": "test"}
    if project_id:
        body["project_id"] = project_id
    resp = await client.post("/api/todos", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestPipelineModeGuard:
    """FREE/MODERATE 模式 todo 调 pipeline 写操作 → 409。"""

    async def test_free_mode_blocks_start_pipeline(self, client: AsyncClient, free_project):
        todo_id = await _create_todo(client, free_project)
        resp = await client.post(f"/api/todos/{todo_id}/pipeline/start")
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"

    async def test_free_mode_blocks_start_phase(self, client: AsyncClient, free_project):
        todo_id = await _create_todo(client, free_project)
        resp = await client.post(f"/api/todos/{todo_id}/phases/clarification/start")
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"

    async def test_free_mode_blocks_confirm_phase(self, client: AsyncClient, free_project):
        todo_id = await _create_todo(client, free_project)
        resp = await client.post(f"/api/todos/{todo_id}/phases/clarification/confirm")
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"

    async def test_free_mode_blocks_skip_phase(self, client: AsyncClient, free_project):
        todo_id = await _create_todo(client, free_project)
        resp = await client.post(f"/api/todos/{todo_id}/phases/clarification/skip")
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"

    async def test_free_mode_blocks_rollback(self, client: AsyncClient, free_project):
        todo_id = await _create_todo(client, free_project)
        resp = await client.post(
            f"/api/todos/{todo_id}/pipeline/rollback",
            json={"target_phase": "clarification"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"

    async def test_moderate_mode_also_blocks(self, client: AsyncClient):
        """MODERATE 同样不可用 pipeline 写操作 (仅 STRICT 放行)。"""
        resp = await client.post("/api/projects", json={
            "name": "moderate-project", "process_constraint": "moderate",
        })
        project_id = resp.json()["id"]
        todo_id = await _create_todo(client, project_id)
        resp = await client.post(f"/api/todos/{todo_id}/pipeline/start")
        assert resp.status_code == 409
        assert resp.json()["detail"]["type"] == "mode_mismatch"


class TestPipelineModeGuardAllowed:
    """STRICT 模式 + 读操作不被守卫拦截。"""

    async def test_strict_mode_allows_start_pipeline(
        self, client: AsyncClient, strict_project
    ):
        todo_id = await _create_todo(client, strict_project)
        resp = await client.post(f"/api/todos/{todo_id}/pipeline/start")
        # STRICT 放行: 后续可能是 200, 也可能后续逻辑报 409/500, 但绝不能是 mode_mismatch
        if resp.status_code == 409:
            assert resp.json().get("detail", {}).get("type") != "mode_mismatch", (
                f"STRICT 误判为 mode_mismatch: {resp.text}"
            )

    async def test_free_mode_allows_read_pipeline(self, client: AsyncClient, free_project):
        """读操作 get_pipeline 跨模式共享, 不被守卫拦截。"""
        todo_id = await _create_todo(client, free_project)
        resp = await client.get(f"/api/todos/{todo_id}/pipeline")
        assert resp.status_code != 409

    async def test_free_mode_allows_list_artifacts(self, client: AsyncClient, free_project):
        """artifact 操作跨模式共享, 不被守卫拦截。"""
        todo_id = await _create_todo(client, free_project)
        resp = await client.get(f"/api/todos/{todo_id}/artifacts")
        assert resp.status_code != 409

    async def test_projectless_todo_defaults_strict(self, client: AsyncClient):
        """无 project 的独立 todo 回退 execution_mode (默认 PIPELINE→strict), 放行。"""
        todo_id = await _create_todo(client, project_id=None)
        resp = await client.post(f"/api/todos/{todo_id}/pipeline/start")
        if resp.status_code == 409:
            assert resp.json().get("detail", {}).get("type") != "mode_mismatch", (
                f"独立 todo 误判为 mode_mismatch: {resp.text}"
            )
