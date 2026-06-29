"""MCP 能力加载器 (v6.17 T4) — 从 MCP capability 加载 tool_specs。

config.transport 决定传输:
- "stdio"/缺省: 启动子进程 (command + args)
- "http"/"sse": HTTP POST (url + headers)

调 McpClient.list_tools → 转 ToolSpec(source=mcp, name, description, parameters=inputSchema)。
连接失败/非 mcp/无 name 工具 → 跳过 (调用方 graceful skip, 不阻断)。
"""
from __future__ import annotations

import logging

from arc.application.capability.mcp_client import (
    HttpMcpTransport,
    McpClient,
    McpTransport,
    StdioMcpTransport,
)
from arc.domain.capability.value_objects import Capability, ToolSource, ToolSpec

logger = logging.getLogger(__name__)


class McpLoader:
    """从 MCP capability 加载工具规格 (v6.17)。"""

    def __init__(self, client_factory=None):
        # client_factory 可注入 (测试用), 缺省按 config 创建真实 McpClient
        self._client_factory = client_factory or self._default_client

    async def load(self, capability: Capability) -> list[ToolSpec]:
        if not capability.is_mcp:
            return []
        config = capability.config or {}
        client = self._client_factory(config)
        try:
            tools = await client.list_tools()
        except Exception as exc:
            logger.warning("McpLoader load failed for %s: %s", capability.name, exc)
            return []
        finally:
            try:
                await client.close()
            except Exception:
                pass
        return [
            self._to_spec(t)
            for t in tools
            if isinstance(t, dict) and t.get("name")
        ]

    def _default_client(self, config: dict) -> McpClient:
        return McpClient(self._create_transport(config))

    @staticmethod
    def _create_transport(config: dict) -> McpTransport:
        transport_type = config.get("transport", "stdio")
        if transport_type == "stdio":
            command = config.get("command")
            if not command:
                raise ValueError("stdio MCP 需要 command")
            return StdioMcpTransport(command, config.get("args"), config.get("env"))
        if transport_type in ("http", "sse"):
            url = config.get("url")
            if not url:
                raise ValueError("http MCP 需要 url")
            return HttpMcpTransport(url, config.get("headers"))
        raise ValueError(f"未知 MCP transport: {transport_type}")

    @staticmethod
    def _to_spec(raw: dict) -> ToolSpec:
        return ToolSpec(
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "") or ""),
            source=ToolSource.MCP,
            parameters=raw.get("inputSchema") or {},
        )
