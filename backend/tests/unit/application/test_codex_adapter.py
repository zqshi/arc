"""CodexAdapter 工具集注入测试 (v6.17 T3).

测 _build_tools: code_interpreter 兼容 + inline function 注册 (Responses API 顶层格式)。
mcp 工具由 T5 处理, 此处跳过。
"""
from arc.application.agent.adapters.codex import CodexAdapter
from arc.domain.capability.value_objects import ToolSource, ToolSpec


def _adapter() -> CodexAdapter:
    return CodexAdapter(api_key="fake", base_url="http://localhost/v1")


class TestBuildTools:
    def test_no_tools_returns_code_interpreter_only(self) -> None:
        tools = _adapter()._build_tools([])
        assert tools == [{"type": "code_interpreter"}]

    def test_inline_function_registered(self) -> None:
        spec = ToolSpec(
            name="search_docs",
            description="搜索文档",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        tools = _adapter()._build_tools([spec])
        assert tools[0] == {"type": "code_interpreter"}
        assert tools[1] == {
            "type": "function",
            "name": "search_docs",
            "description": "搜索文档",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        }

    def test_inline_without_parameters_defaults_to_object(self) -> None:
        spec = ToolSpec(name="noop", description="无参")
        tools = _adapter()._build_tools([spec])
        fn = tools[1]
        assert fn["parameters"] == {"type": "object", "properties": {}}

    def test_mcp_tool_skipped(self) -> None:
        spec = ToolSpec(name="mcp_tool", source=ToolSource.MCP, server_ref="mcp-1")
        tools = _adapter()._build_tools([spec])
        assert tools == [{"type": "code_interpreter"}]

    def test_multiple_inline_tools(self) -> None:
        specs = [ToolSpec(name="t1"), ToolSpec(name="t2")]
        tools = _adapter()._build_tools(specs)
        assert len(tools) == 3  # code_interpreter + 2 functions
        assert tools[1]["name"] == "t1"
        assert tools[2]["name"] == "t2"
