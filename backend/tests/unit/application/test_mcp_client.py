"""McpClient 测试 (v6.17 T4) — 用 fake transport 验证协议逻辑。"""
import pytest

from arc.application.capability.mcp_client import McpClient, McpError


class FakeTransport:
    def __init__(self, tools=None, error=None):
        self._tools = tools or []
        self._error = error
        self.requests: list = []
        self.closed = False

    async def initialize(self) -> None:
        pass

    async def request(self, method, params=None):
        self.requests.append((method, params))
        if self._error and method == "tools/list":
            raise McpError(self._error)
        if method == "tools/list":
            return {"tools": self._tools}
        if method == "tools/call":
            return {"content": [{"type": "text", "text": "ok"}]}
        return {}

    async def close(self) -> None:
        self.closed = True


class TestMcpClient:
    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        transport = FakeTransport(tools=[
            {"name": "t1", "description": "d", "inputSchema": {"type": "object"}}
        ])
        client = McpClient(transport)
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "t1"
        await client.close()
        assert transport.closed

    @pytest.mark.asyncio
    async def test_list_tools_empty(self) -> None:
        client = McpClient(FakeTransport(tools=[]))
        assert await client.list_tools() == []

    @pytest.mark.asyncio
    async def test_call_tool(self) -> None:
        transport = FakeTransport()
        client = McpClient(transport)
        result = await client.call_tool("t1", {"x": 1})
        assert "content" in result
        assert ("tools/call", {"name": "t1", "arguments": {"x": 1}}) in transport.requests

    @pytest.mark.asyncio
    async def test_list_tools_propagates_error(self) -> None:
        client = McpClient(FakeTransport(error="server down"))
        with pytest.raises(McpError):
            await client.list_tools()
