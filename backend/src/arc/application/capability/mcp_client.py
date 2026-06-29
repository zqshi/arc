"""MCP 客户端 (v6.17 T4) — 消费外部 MCP server 的工具。

支持两种传输:
- stdio: 启动子进程, stdin/stdout 行分隔 JSON-RPC (MCP 标准本地传输)
- http: HTTP POST JSON-RPC (streamable HTTP) — v6.18 支持 SSE 流式响应
  (text/event-stream 逐条 data: 推 JSON-RPC), 兼容普通 application/json 单次响应

协议: JSON-RPC 2.0。initialize handshake → tools/list (返回工具列表) → tools/call。
McpClient 封装传输, 提供 list_tools/call_tool; McpLoader 调它加载 tool_specs。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

_MCP_PROTOCOL_VERSION = "2024-11-05"
_REQUEST_TIMEOUT = 30.0


class McpError(Exception):
    """MCP 调用错误 (JSON-RPC error 或传输失败)。"""


class McpTransport(Protocol):
    """MCP 传输接口 (v6.17)。"""

    async def initialize(self) -> None: ...
    async def request(self, method: str, params: dict | None) -> dict: ...
    async def close(self) -> None: ...


class StdioMcpTransport:
    """stdio 传输: 启动子进程, stdin/stdout 行分隔 JSON-RPC。"""

    def __init__(
        self, command: str, args: list[str] | None = None, env: dict | None = None
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader: asyncio.Task | None = None

    async def initialize(self) -> None:
        if self._process:
            return
        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        self._reader = asyncio.create_task(self._read_loop())
        await self.request("initialize", {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "arc", "version": "1.0"},
        })
        await self._notify("notifications/initialized")

    async def request(self, method: str, params: dict | None = None) -> dict:
        if not self._process:
            await self.initialize()
        self._next_id += 1
        req_id = self._next_id
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = future
        await self._send({
            "jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {},
        })
        try:
            return await asyncio.wait_for(future, timeout=_REQUEST_TIMEOUT)
        except asyncio.TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise McpError(f"MCP request '{method}' timed out") from exc

    async def _notify(self, method: str, params: dict | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, msg: dict) -> None:
        assert self._process and self._process.stdin
        data = (json.dumps(msg) + "\n").encode()
        self._process.stdin.write(data)
        await self._process.stdin.drain()

    async def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            req_id = msg.get("id")
            if req_id is None:
                continue  # notification, ignore
            future = self._pending.pop(int(req_id), None)
            if future is None or future.done():
                continue
            if "error" in msg:
                future.set_exception(McpError(str(msg["error"])))
            else:
                future.set_result(msg.get("result", {}))

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()


class HttpMcpTransport:
    """HTTP 传输 (streamable HTTP): POST JSON-RPC, 读响应。

    v6.18: 支持两种响应形态——
    - SSE 流 (Content-Type: text/event-stream): 服务端逐条 `data: <json>\\n\\n` 推
      JSON-RPC 消息, 本端解析出匹配 req_id 的那条 (跳过其他 id / notification)。
      streamable HTTP MCP server 的标准形态。
    - 普通 JSON (Content-Type: application/json): 单次请求/响应, 整个 body 为单个
      JSON-RPC response。向后兼容 v6.17 简化实现。
    """

    def __init__(self, url: str, headers: dict | None = None) -> None:
        self._url = url
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._next_id = 0
        self._initialized = False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"Content-Type": "application/json", **self._headers},
                timeout=_REQUEST_TIMEOUT,
            )
        return self._client

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self.request("initialize", {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "arc", "version": "1.0"},
        })
        client = self._get_client()
        await client.post(self._url, json={
            "jsonrpc": "2.0", "method": "notifications/initialized",
        })
        self._initialized = True

    async def request(self, method: str, params: dict | None = None) -> dict:
        if not self._initialized and method != "initialize":
            await self.initialize()
        self._next_id += 1
        req_id = self._next_id
        client = self._get_client()
        resp = await client.post(self._url, json={
            "jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {},
        })
        resp.raise_for_status()
        return _parse_mcp_response(resp, req_id)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _parse_mcp_response(resp: httpx.Response, req_id: int) -> dict:
    """从 HTTP 响应解析匹配 req_id 的 JSON-RPC result。

    SSE 流: 按行扫描 `data:` 行, 解析每条 JSON, 取 id 匹配的那条 (跳过其他 id /
    notification / 心跳)。普通 JSON: 整个 body 单个 response。
    解析失败 / error → McpError。
    """
    content_type = resp.headers.get("content-type", "")
    body = resp.content

    if "text/event-stream" in content_type:
        for msg in _iter_sse_messages(body):
            if msg.get("id") != req_id:
                continue  # 别的请求/通知, 跳过
            if "error" in msg:
                raise McpError(str(msg["error"]))
            return msg.get("result", {})
        raise McpError(f"SSE 流中无匹配 id={req_id} 的响应")

    # 普通 application/json: 单次响应
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise McpError(f"MCP 响应非合法 JSON: {exc}") from exc
    if "error" in data:
        raise McpError(str(data["error"]))
    return data.get("result", {})


def _iter_sse_messages(body: bytes):
    """解析 SSE 事件流, 产出每条 data: 负载反序列化后的 dict。

    SSE 格式: `event: <name>\\n` `data: <json>\\n` `\\n` (空行分隔事件)。
    data 可跨多行 (每行一个 data:), 本实现按行累积后合并。忽略 event/id 等其他字段
    (JSON-RPC id 在 data 负载内, 不取 SSE 的 id 字段)。
    """
    data_lines: list[str] = []
    for raw in body.splitlines():
        line = raw.decode(errors="replace")
        if line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
        elif line == "":
            if data_lines:
                payload = "\n".join(data_lines)
                data_lines = []
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    continue
        # 其他行 (event:/id:/注释) 忽略
    # 流末尾若无空行收尾, 处理剩余
    if data_lines:
        payload = "\n".join(data_lines)
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            pass


class McpClient:
    """MCP 客户端 — 封装传输, 提供工具列表/调用 (v6.17)。"""

    def __init__(self, transport: McpTransport) -> None:
        self._transport = transport

    async def list_tools(self) -> list[dict]:
        """返回 MCP server 暴露的工具列表 (raw: name/description/inputSchema)。"""
        result = await self._transport.request("tools/list", {})
        return result.get("tools", []) if isinstance(result, dict) else []

    async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """调用 MCP 工具, 返回结果。"""
        result = await self._transport.request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        return result if isinstance(result, dict) else {"result": result}

    async def close(self) -> None:
        await self._transport.close()
