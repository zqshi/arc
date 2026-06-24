"""ToolLoop 指标与事件数据类 (v5.8.0 从 tool_loop.py 拆分)。

纯数据类, 无业务逻辑。tool_loop.py re-export 保持 import 兼容。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# 工具循环安全限制
MAX_TOOL_ROUNDS = 25  # 单次响应最大 tool-use 往返次数
MAX_TOOL_TOKENS = 200000  # tool-use 对话 token 预算
TOOL_TIMEOUT_SECONDS = 600  # 安全网 — 工具自身有更短 timeout (run_command 300s)
TOOL_MAX_RETRIES = 1  # 瞬时失败重试次数

# 只读工具 — 可并发执行
READONLY_TOOLS = frozenset({"read_file", "list_directory", "grep_search"})


@dataclass
class ToolLoopMetrics:
    """Tracks statistics for a tool-aware generation cycle."""

    loop_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    tool_rounds: int = 0
    total_tokens: int = 0
    elapsed_ms: int = 0
    final_state: str = ""


@dataclass
class ToolLoopEvent:
    """Events emitted during tool-aware generation.

    type 取值:
      "text_delta"   — 流式文本块
      "tool_call"    — LLM 调用工具
      "tool_result"  — 工具执行完成
      "thinking"     — LLM 思考中 (tool call 前)
      "complete"     — 生成结束
      "error"        — 出错
    """

    type: str
    content: str = ""
    metadata: dict = field(default_factory=dict)
