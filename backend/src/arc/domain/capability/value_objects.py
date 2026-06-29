"""能力注册表值对象 (v6.8.0 W1)。

能力 (agent/skill) 声明的领域模型。capability 是注册表项, 不具生命周期行为,
故为值对象而非实体 (与 deployment/signer 的 SigningCredentials 同构)。

config 按 type 语义不同:
- agent: {adapter, model, ...} (env 配置迁移, W2)
- skill: {directory, ...} (SKILL.md 所在目录, W2 加载器读取)
- mcp: 预留扩展位, 本期不实现 loader
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from arc.domain.capability.errors import CapabilityError


class CapabilityType(StrEnum):
    """能力类型。"""

    AGENT = "agent"  # 外部编码 agent (OpenHands/Codex/Claude Code/Cursor)
    SKILL = "skill"  # SKILL.md 能力封装 (prompt+工具集)
    MCP = "mcp"  # MCP server 能力 (v6.17 由 McpLoader 实现)


class CapabilityStatus(StrEnum):
    """能力声明状态。"""

    ACTIVE = "active"  # 启用, 可被环节配置引用
    DISABLED = "disabled"  # 禁用, 不参与注入/门禁


class CapabilityScope(StrEnum):
    """能力作用域。"""

    GLOBAL = "global"  # 全租户可用 (系统级能力)
    PROJECT = "project"  # 项目级私有 (项目自建能力)


CAPABILITY_TYPE_LABELS: dict[CapabilityType, str] = {
    CapabilityType.AGENT: "Agent",
    CapabilityType.SKILL: "Skill",
    CapabilityType.MCP: "MCP",
}


@dataclass(frozen=True)
class Capability:
    """能力声明 — agent/skill 的可管理、可配置能力 (注册表项)。

    注册表项不具生命周期行为, 故为值对象。config 为配置载荷 (JSONB 语义),
    按 type 由对应 loader 解释 (W2)。scope 区分系统级与项目级。
    """

    id: uuid.UUID
    name: str
    type: CapabilityType
    config: dict[str, Any] = field(default_factory=dict)
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    scope: CapabilityScope = CapabilityScope.GLOBAL

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise CapabilityError("能力 name 不能为空")

    @property
    def is_active(self) -> bool:
        """是否启用 (可被环节配置引用)。"""
        return self.status == CapabilityStatus.ACTIVE

    @property
    def is_agent(self) -> bool:
        return self.type == CapabilityType.AGENT

    @property
    def is_skill(self) -> bool:
        return self.type == CapabilityType.SKILL

    @property
    def is_mcp(self) -> bool:
        """v6.17: MCP 能力 (由 McpLoader 加载工具列表)。"""
        return self.type == CapabilityType.MCP


class ToolSource(StrEnum):
    """工具来源 (v6.17)。

    - inline: skill 自带的 function 工具定义 (parameters 为 JSON schema)
    - mcp: 引用外部 MCP server 提供的工具 (server_ref 指向 MCP capability)
    """

    INLINE = "inline"
    MCP = "mcp"


@dataclass(frozen=True)
class ToolSpec:
    """工具规格 — skill 工具集的最小单元 (v6.17)。

    值对象, 不可变。inline 工具用 parameters (JSON schema); mcp 工具用
    server_ref (指向 MCP capability id 或 server url)。两类来源按 agent
    能力分发注入 (Codex 注册 function / OpenHands+Claude Code 转指引文本)。
    """

    name: str
    description: str = ""
    source: ToolSource = ToolSource.INLINE
    parameters: dict[str, Any] = field(default_factory=dict)
    server_ref: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise CapabilityError("工具 name 不能为空")

    @property
    def is_inline(self) -> bool:
        return self.source == ToolSource.INLINE

    @property
    def is_mcp(self) -> bool:
        return self.source == ToolSource.MCP
