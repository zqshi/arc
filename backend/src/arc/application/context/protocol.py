"""上下文注入协议 — 统一的 ContextProvider 接口与 ContextSegment 数据模型。

设计原则：
- 每种上下文来源实现 ContextProvider 接口
- ContextAssembler 按优先级和 token 预算组装
- 阶段感知：不同 phase 对不同上下文来源分配不同 budget
- 可扩展：新增上下文来源 = 写一个 Provider + 注册
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from arc.domain.conversation.entity import Conversation
from arc.domain.project.entity import Project
from arc.domain.todo.entity import Todo


@dataclass
class ContextRequest:
    """上下文请求 — 携带所有决策所需信息。

    Provider 从这里获取必要的信息来构建自己的上下文片段。
    """

    todo: Todo | None
    conversation: Conversation
    phase: str  # "clarification" | "ui_design" | "architecture" | "development" | "testing"
    completed_artifacts: list[str] = field(default_factory=list)
    project: Project | None = None
    project_id: uuid.UUID | None = None


@dataclass
class ContextSegment:
    """上下文片段 — 可组装的最小单元。

    priority 说明:
      0 = 不可压缩（系统指令、身份声明）
      1 = 高优（领域模型、评审反馈、代码能力）
      2 = 中优（方法论、充分性提示）
      3 = 可丢弃（参考模式、冗余经验）
    """

    source: str  # provider 来源标识
    priority: int  # 0-3
    content: str
    token_estimate: int = 0  # 延迟计算
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.token_estimate and self.content:
            from arc.application.context.controller import estimate_tokens
            self.token_estimate = estimate_tokens(self.content)


@runtime_checkable
class ContextProvider(Protocol):
    """上下文提供者接口。

    每个实现负责一种上下文来源的获取和格式化。
    实现者保证：
    - provide() 方法是幂等的
    - 异常时返回空列表（不抛出）
    - 尊重 ContextRequest.phase 进行选择性注入
    """

    source: str  # 唯一标识，如 "project", "domain_model", "review_feedback"

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        """获取上下文片段列表。"""
        ...


# ── 阶段感知的 Token 预算配置 ────────────────────────────

PHASE_BUDGETS: dict[str, dict[str, int]] = {
    "clarification": {
        "project": 2000,
        "domain_model": 2000,
        "review_feedback": 1500,
        "experience": 8000,
        "methodology": 4000,
        "code_capability": 500,
        "deliverable": 2000,
        "sufficiency": 500,
    },
    "ui_design": {
        "project": 2000,
        "domain_model": 3000,
        "review_feedback": 2000,
        "experience": 4000,
        "methodology": 4000,
        "code_capability": 500,
        "deliverable": 2000,
        "sufficiency": 0,
    },
    "architecture": {
        "project": 2000,
        "domain_model": 8000,
        "review_feedback": 4000,
        "experience": 4000,
        "methodology": 4000,
        "code_capability": 1000,
        "deliverable": 2000,
        "sufficiency": 0,
    },
    "development": {
        "project": 2000,
        "domain_model": 6000,
        "review_feedback": 4000,
        "experience": 3000,
        "methodology": 3000,
        "code_capability": 2000,
        "deliverable": 2000,
        "sufficiency": 0,
    },
    "testing": {
        "project": 2000,
        "domain_model": 4000,
        "review_feedback": 2000,
        "experience": 3000,
        "methodology": 3000,
        "code_capability": 2000,
        "deliverable": 2000,
        "sufficiency": 0,
    },
}

# 默认预算 — phase 不在 PHASE_BUDGETS 中时使用
DEFAULT_BUDGET: dict[str, int] = {
    "project": 2000,
    "domain_model": 4000,
    "review_feedback": 2000,
    "experience": 5000,
    "methodology": 3000,
    "code_capability": 1000,
    "deliverable": 2000,
    "sufficiency": 500,
}


def get_source_budget(phase: str, source: str) -> int:
    """获取指定阶段+来源的 token 预算。"""
    budget_map = PHASE_BUDGETS.get(phase, DEFAULT_BUDGET)
    return budget_map.get(source, 2000)
