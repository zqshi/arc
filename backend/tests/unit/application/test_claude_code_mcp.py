"""ClaudeCodeAdapter MCP 配置注入测试 (v6.17 T5)."""
import json

from arc.application.agent.adapters.claude_code import ClaudeCodeAdapter


class TestWriteMcpConfig:
    def test_no_servers_returns_none(self) -> None:
        assert ClaudeCodeAdapter._write_mcp_config([]) is None

    def test_stdio_server(self) -> None:
        path = ClaudeCodeAdapter._write_mcp_config([
            {"name": "fs", "transport": "stdio", "command": "npx",
             "args": ["-y", "fs-mcp"], "env": {"X": "1"}},
        ])
        assert path is not None
        with open(path) as f:
            cfg = json.load(f)
        assert cfg["mcpServers"]["fs"] == {
            "command": "npx", "args": ["-y", "fs-mcp"], "env": {"X": "1"},
        }

    def test_http_server(self) -> None:
        path = ClaudeCodeAdapter._write_mcp_config([
            {"name": "api", "transport": "http", "url": "http://localhost:8080",
             "headers": {"Authorization": "Bearer x"}},
        ])
        with open(path) as f:
            cfg = json.load(f)
        assert cfg["mcpServers"]["api"]["type"] == "http"
        assert cfg["mcpServers"]["api"]["url"] == "http://localhost:8080"
        assert cfg["mcpServers"]["api"]["headers"]["Authorization"] == "Bearer x"

    def test_multiple_servers(self) -> None:
        path = ClaudeCodeAdapter._write_mcp_config([
            {"name": "a", "transport": "stdio", "command": "a"},
            {"name": "b", "transport": "http", "url": "http://b"},
        ])
        with open(path) as f:
            cfg = json.load(f)
        assert len(cfg["mcpServers"]) == 2
        assert "a" in cfg["mcpServers"]
        assert "b" in cfg["mcpServers"]
