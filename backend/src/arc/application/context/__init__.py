"""Context 模块 — 上下文控制、压缩与统一组装。

Harness §2 Context Control + §3 Compression 的实现。
v5.4+ 新增 ContextProvider 协议和 ContextAssembler。
"""

from arc.application.context.assembler import ContextAssembler
from arc.application.context.compression import CompressionManager
from arc.application.context.controller import ContextController
from arc.application.context.prompt_builder import PromptBuilder
from arc.application.context.protocol import (
    ContextProvider,
    ContextRequest,
    ContextSegment,
)

__all__ = [
    "ContextController",
    "CompressionManager",
    "PromptBuilder",
    "ContextAssembler",
    "ContextProvider",
    "ContextRequest",
    "ContextSegment",
]
