"""ClaudeCodeAdapter MCP 配置注入测试 (v6.17 T5) + 临时文件生命周期清理 (v6.18)。"""
import asyncio
import json
import os

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
        os.unlink(path)  # v6.18: 测试侧自清

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
        os.unlink(path)

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
        os.unlink(path)


class TestMcpConfigLifecycle:
    """v6.18: mcp_config 临时文件生命周期清理。

    原 v6.17 _write_mcp_config 写临时文件后无清理, 靠 OS tmpdir 兜底。长期运行累积
    arc-mcp-*.json。v6.18 将 path 绑定到 _Session, _read_output 正常结束 / close()
    兜底都删文件。
    """

    def _make_session(self, path):
        """构造一个挂了 mcp_config_path 的 _Session (不真起进程)。"""
        from arc.application.agent.adapters.claude_code import _Session
        session = _Session.__new__(_Session)
        session.mcp_config_path = path
        session.stdout_lines = []
        session.stderr_lines = []
        session.read_task = None
        session.finished = False
        session.return_code = None
        # 桩进程: cancel 路径 (send_signal/wait/kill) 可跑完
        class _StubProc:
            def send_signal(self, sig): pass
            async def wait(self): return 0
            def kill(self): pass
            returncode = 0
        session.process = _StubProc()
        return session

    def test_close_removes_temp_file(self) -> None:
        """close() 兜底删除残留 mcp_config 临时文件。"""
        path = ClaudeCodeAdapter._write_mcp_config([
            {"name": "fs", "transport": "stdio", "command": "npx"},
        ])
        assert path is not None and os.path.exists(path)

        adapter = ClaudeCodeAdapter()
        session = self._make_session(path)
        adapter._sessions["s1"] = session

        asyncio.run(adapter.close())

        assert not os.path.exists(path), "close() 后临时文件应已删除"

    def test_read_output_cleans_on_finish(self) -> None:
        """_read_output 正常读完输出后删 mcp_config 临时文件。"""
        path = ClaudeCodeAdapter._write_mcp_config([
            {"name": "fs", "transport": "stdio", "command": "npx"},
        ])
        assert os.path.exists(path)

        adapter = ClaudeCodeAdapter()
        session = self._make_session(path)
        adapter._sessions["s1"] = session
        # 覆盖进程为 stdout/stderr 立即 EOF 的桩 (readline 返回 b"" 即 EOF)
        class _StubStream:
            async def readline(self): return b""
        class _StubProc:
            stdout = _StubStream()
            stderr = _StubStream()
            async def wait(self): return 0
        session.process = _StubProc()

        asyncio.run(adapter._read_output("s1"))

        assert session.finished
        assert not os.path.exists(path), "_read_output 结束后临时文件应已删除"

    def test_close_handles_no_temp_file_gracefully(self) -> None:
        """session 无 mcp_config_path 时 close() 不报错 (无文件可删)。"""
        adapter = ClaudeCodeAdapter()
        session = self._make_session(None)
        adapter._sessions["s1"] = session

        asyncio.run(adapter.close())  # 不应抛异常
