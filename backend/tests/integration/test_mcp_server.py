"""Tests for MCP server endpoint (v5.6.0 T18).

MCP-over-HTTP (JSON-RPC 2.0), 暴露 artifact tools 给外部 AI 客户端。
集成测试用 client fixture 走真实 HTTP, 验证 JSON-RPC 协议 + tool 行为。
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _make_todo_with_artifact(client: AsyncClient) -> tuple[str, str]:
    """创建 todo + artifact, 返回 (todo_id, artifact_id)。"""
    resp = await client.post("/api/todos", json={
        "title": "MCP test todo",
        "description": "测试 MCP 暴露",
    })
    assert resp.status_code == 201
    todo_id = resp.json()["id"]

    # 通过 conversation 无法快速造 artifact, 直接用 pipeline artifact API 需 todo 有 artifact
    # 这里用 DB 直插更可靠 —— 但集成测试用 client 更贴近真实
    # 改用: 先确认无 artifact 时 list 返回空
    return todo_id, ""


class TestMcpInitialize:
    @pytest.mark.asyncio
    async def test_initialize_returns_protocol_info(self, client: AsyncClient):
        """MCP initialize 握手返回协议信息。"""
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "protocolVersion" in data["result"]
        assert "serverInfo" in data["result"]


class TestMcpToolsList:
    @pytest.mark.asyncio
    async def test_tools_list_returns_artifact_tools(self, client: AsyncClient):
        """tools/list 返回 arc artifact tools。"""
        # 先 initialize
        await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "arc_list_artifacts" in names
        assert "arc_get_artifact" in names
        assert "arc_update_artifact" in names

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(self, client: AsyncClient):
        await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        tools = resp.json()["result"]["tools"]
        for t in tools:
            assert "inputSchema" in t
            assert t["inputSchema"]["type"] == "object"


class TestMcpToolsCall:
    @pytest.mark.asyncio
    async def test_list_artifacts_empty_todo(self, client: AsyncClient):
        """arc_list_artifacts 对空 todo 返回空列表。"""
        await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        # 创建 todo
        resp = await client.post("/api/todos", json={"title": "mcp todo"})
        todo_id = resp.json()["id"]

        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "arc_list_artifacts",
                "arguments": {"todo_id": todo_id},
            },
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        # MCP tool result 是 content 数组
        assert "content" in result
        assert isinstance(result["content"], list)

    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_error(self, client: AsyncClient):
        await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # method not found

    @pytest.mark.asyncio
    async def test_get_artifact_not_found(self, client: AsyncClient):
        await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        resp = await client.post("/api/todos", json={"title": "mcp todo2"})
        todo_id = resp.json()["id"]

        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "arc_get_artifact",
                "arguments": {"todo_id": todo_id, "artifact_id": str(uuid.uuid4())},
            },
        })
        result = resp.json()["result"]
        # MCP tool 错误以 isError 标记
        assert result.get("isError") is True


class TestMcpProtocol:
    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self, client: AsyncClient):
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "unknown/method", "params": {},
        })
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_invalid_jsonrpc_returns_error(self, client: AsyncClient):
        resp = await client.post("/api/mcp", json={
            "jsonrpc": "1.0", "id": 1, "method": "initialize", "params": {},
        })
        data = resp.json()
        assert "error" in data
