"""McpLoader 测试 (v6.17 T4) — 用 fake client 验证转换与降级。"""
import uuid

import pytest

from arc.application.capability.mcp_client import (
    HttpMcpTransport,
    StdioMcpTransport,
)
from arc.application.capability.mcp_loader import McpLoader
from arc.domain.capability.value_objects import Capability, CapabilityType


def _mcp(config: dict) -> Capability:
    return Capability(id=uuid.uuid4(), name="mcp-srv", type=CapabilityType.MCP, config=config)


class FakeClient:
    def __init__(self, tools=None, raises=False):
        self._tools = tools or []
        self._raises = raises
        self.closed = False

    async def list_tools(self):
        if self._raises:
            raise RuntimeError("conn failed")
        return self._tools

    async def close(self) -> None:
        self.closed = True


class TestMcpLoader:
    @pytest.mark.asyncio
    async def test_load_converts_to_tool_specs(self) -> None:
        tools = [{"name": "search", "description": "搜索", "inputSchema": {"type": "object"}}]
        loader = McpLoader(client_factory=lambda c: FakeClient(tools=tools))
        specs = await loader.load(_mcp({"transport": "stdio", "command": "node"}))
        assert len(specs) == 1
        assert specs[0].name == "search"
        assert specs[0].is_mcp
        assert specs[0].parameters == {"type": "object"}

    @pytest.mark.asyncio
    async def test_load_non_mcp_returns_empty(self) -> None:
        cap = Capability(id=uuid.uuid4(), name="skill", type=CapabilityType.SKILL, config={})
        loader = McpLoader(client_factory=lambda c: FakeClient())
        assert await loader.load(cap) == []

    @pytest.mark.asyncio
    async def test_load_connection_failure_returns_empty(self) -> None:
        loader = McpLoader(client_factory=lambda c: FakeClient(raises=True))
        specs = await loader.load(_mcp({"transport": "stdio", "command": "node"}))
        assert specs == []

    @pytest.mark.asyncio
    async def test_load_closes_client(self) -> None:
        client = FakeClient(tools=[])
        loader = McpLoader(client_factory=lambda c: client)
        await loader.load(_mcp({"transport": "stdio", "command": "node"}))
        assert client.closed

    @pytest.mark.asyncio
    async def test_load_skips_tools_without_name(self) -> None:
        tools = [{"name": "ok"}, {"description": "无名"}]
        loader = McpLoader(client_factory=lambda c: FakeClient(tools=tools))
        specs = await loader.load(_mcp({"transport": "http", "url": "http://x"}))
        assert len(specs) == 1
        assert specs[0].name == "ok"

    def test_create_transport_stdio(self) -> None:
        t = McpLoader._create_transport({"transport": "stdio", "command": "node", "args": ["s.js"]})
        assert isinstance(t, StdioMcpTransport)

    def test_create_transport_http(self) -> None:
        t = McpLoader._create_transport({"transport": "http", "url": "http://localhost"})
        assert isinstance(t, HttpMcpTransport)

    def test_create_transport_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            McpLoader._create_transport({"transport": "weird"})

    def test_create_transport_stdio_missing_command_raises(self) -> None:
        with pytest.raises(ValueError):
            McpLoader._create_transport({"transport": "stdio"})
