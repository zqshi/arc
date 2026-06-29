"""McpClient 测试 (v6.17 T4) — 用 fake transport 验证协议逻辑。"""
import json

import httpx
import pytest

from arc.application.capability.mcp_client import (
    HttpMcpTransport,
    McpClient,
    McpError,
)


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


def _sse_response(req_id: int, result: dict) -> bytes:
    """构造一条 SSE 事件流 (text/event-stream), data: 单行 JSON-RPC response。"""
    payload = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})
    return f"event: message\ndata: {payload}\n\n".encode()


class TestHttpMcpTransportSse:
    """v6.18: HttpMcpTransport SSE 流式响应解析 (transport=sse 已被 mcp_loader 路由到此)。

    背景: streamable HTTP MCP server 用 Content-Type: text/event-stream 逐条 data: 推
    JSON-RPC 响应。原实现用 resp.json() 读整个响应体为单个 JSON, 在 SSE 下要么解析失败
    要么拿不到匹配 req_id 的那条。属契约不一致 (config transport=sse 接通但实现不支持)。
    """

    @pytest.mark.asyncio
    async def test_sse_response_parsed_not_whole_body(self) -> None:
        """SSE 流: request 应从 event-stream 中解析匹配 id 的 JSON-RPC, 非 resp.json()。"""
        transport = HttpMcpTransport("http://localhost:8080/mcp")

        def handler(request: httpx.Request) -> httpx.Response:
            # initialize (id=1) + tools/list (id=2) 都返回 SSE 流
            body = json.loads(request.content)
            req_id = body["id"]
            if body["method"] == "initialize":
                return httpx.Response(
                    200,
                    headers={"content-type": "text/event-stream"},
                    content=_sse_response(req_id, {"protocolVersion": "2024-11-05"}),
                )
            return httpx.Response(
                200,
                    headers={"content-type": "text/event-stream"},
                    content=_sse_response(req_id, {"tools": [{"name": "echo"}]}),
            )

        transport._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Content-Type": "application/json"},
        )
        transport._initialized = True  # 跳过 initialize, 直测 request 解析

        result = await transport.request("tools/list", {})
        assert result == {"tools": [{"name": "echo"}]}
        await transport.close()

    @pytest.mark.asyncio
    async def test_sse_skips_unmatched_ids(self) -> None:
        """SSE 流含其他 id 的消息时, 应跳过只取匹配 id 的那条。"""
        transport = HttpMcpTransport("http://localhost:8080/mcp")

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            req_id = body["id"]
            # 流里先塞一条别的 id 的消息, 再塞匹配的
            content = _sse_response(999, {"unrelated": True}) + _sse_response(
                req_id, {"ok": True}
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=content,
            )

        transport._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Content-Type": "application/json"},
        )
        transport._initialized = True

        result = await transport.request("tools/list", {})
        assert result == {"ok": True}
        await transport.close()

    @pytest.mark.asyncio
    async def test_sse_error_response_raises(self) -> None:
        """SSE 流带 JSON-RPC error 时, 应抛 McpError。"""
        transport = HttpMcpTransport("http://localhost:8080/mcp")

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            req_id = body["id"]
            err = json.dumps(
                {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "bad"}}
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=f"data: {err}\n\n".encode(),
            )

        transport._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Content-Type": "application/json"},
        )
        transport._initialized = True

        with pytest.raises(McpError):
            await transport.request("tools/list", {})
        await transport.close()

    @pytest.mark.asyncio
    async def test_plain_json_response_still_works(self) -> None:
        """非 SSE (content-type: application/json) 单次响应向后兼容。"""
        transport = HttpMcpTransport("http://localhost:8080/mcp")

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {"ok": 1}}).encode(),
            )

        transport._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Content-Type": "application/json"},
        )
        transport._initialized = True

        assert await transport.request("tools/list", {}) == {"ok": 1}
        await transport.close()
