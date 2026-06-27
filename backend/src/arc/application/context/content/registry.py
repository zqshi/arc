"""content 内容注册表统一入口 (B方案/T5)。

集中 re-export content 各模块 (methodology / phase_prompts / gate) 的内容符号,
作为内容读取的统一入口。新消费方优先 from arc.application.context.content.registry import ...;
既有消费方读各子模块亦兼容 (re-export 透明)。

复用 v6.9 dict + .get(key, default) fallback 模式 (DELIVERABLES_BY_TYPE 范式)。
内容显性化后, 新增/调整环节逻辑内容 (prompt 文本 / 字段规则 / 阈值 / profile)
集中 content 模块声明管理; 编排逻辑 (路由 / 评估流程 / 子步骤控制) 保持原模块。
"""

from __future__ import annotations

from arc.application.context.content.gate import (  # noqa: F401
    GATE_EVALUATION_PROMPT,
    PROFILES,
    GateProfile,
    get_profile,
)
from arc.application.context.content.methodology import (  # noqa: F401
    FREE_BASELINES,
    MODERATE_PROMPTS,
    PROTOTYPE_BUILD_GUIDES,
    get_prototype_guide,
)
from arc.application.context.content.phase_prompts import (  # noqa: F401
    _PHASE_INFERENCE_PROMPT,
    PHASE_EXTRACTION_PROMPTS,
    PHASE_SYSTEM_PROMPTS,
)

__all__ = [
    # methodology
    "FREE_BASELINES",
    "MODERATE_PROMPTS",
    "PROTOTYPE_BUILD_GUIDES",
    "get_prototype_guide",
    # phase_prompts
    "PHASE_SYSTEM_PROMPTS",
    "PHASE_EXTRACTION_PROMPTS",
    # gate
    "GATE_EVALUATION_PROMPT",
    "PROFILES",
    "GateProfile",
    "get_profile",
]
