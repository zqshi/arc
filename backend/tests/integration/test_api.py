from __future__ import annotations

from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestTodoCRUD:
    async def test_create_and_list(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={
            "title": "集成测试任务",
            "description": "测试创建待办",
            "tags": [{"label": "测试", "color": "#EF4444"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "集成测试任务"
        assert data["status"] == "pending"
        todo_id = data["id"]

        resp = await client.get("/api/todos")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(t["id"] == todo_id for t in items)

    async def test_get_single(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "单条查询"})
        todo_id = resp.json()["id"]

        resp = await client.get(f"/api/todos/{todo_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "单条查询"

    async def test_update(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "待更新"})
        todo_id = resp.json()["id"]

        resp = await client.put(f"/api/todos/{todo_id}", json={
            "title": "已更新",
            "description": "更新后的描述",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "已更新"
        assert resp.json()["description"] == "更新后的描述"

    async def test_delete(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "待删除"})
        todo_id = resp.json()["id"]

        resp = await client.delete(f"/api/todos/{todo_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/todos/{todo_id}")
        assert resp.status_code == 404

    async def test_not_found(self, client: AsyncClient):
        resp = await client.get("/api/todos/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestTodoLifecycle:
    async def test_filter_by_status(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "筛选测试"})
        resp = await client.get("/api/todos?status=pending")
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["status"] == "pending"


class TestExperienceCRUD:
    async def test_create_and_list(self, client: AsyncClient):
        resp = await client.post("/api/experiences", json={
            "title": "测试经验",
            "scope": "project",
            "problem": "遇到问题",
            "solution": "解决方案",
            "decisions": ["决策1"],
            "pitfalls": ["坑1"],
            "tags": [{"label": "测试", "color": "#34D399"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "测试经验"
        assert data["scope"] == "project"

        resp = await client.get("/api/experiences")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_single(self, client: AsyncClient):
        resp = await client.post("/api/experiences", json={
            "title": "查询经验",
            "problem": "p",
            "solution": "s",
        })
        exp_id = resp.json()["id"]

        resp = await client.get(f"/api/experiences/{exp_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "查询经验"
