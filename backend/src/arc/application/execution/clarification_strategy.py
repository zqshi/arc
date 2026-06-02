"""需求澄清策略引擎 — 基于 decision-thinking-toolkit 改造。

来源: decision-thinking-toolkit v1.0 三套工具改造
职责:
  - 根据需求类型自动路由到最佳澄清策略
  - 提供三套递进式方法论的 prompt 注入
  - 与 SufficiencyGate 协同: 先检测充分性，再选策略深化

设计原则:
  - 意图驱动: prompt 只给目标 + 上下文，不给步骤
  - 渐进式: 逐章节引导，不一次性抛出整个框架
  - 动态: 根据对话轮次和需求类型调整深度
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class ClarificationType(StrEnum):
    """需求类型 — 决定使用哪套澄清策略"""

    NEW_DOMAIN = "new_domain"  # 全新领域/方向不明
    FEATURE_REQUEST = "feature_request"  # 明确功能请求
    OPTIMIZATION = "optimization"  # 已有方案待验证/优化
    UNCLEAR = "unclear"  # 信息不足，先做充分性检测


class ClarificationStrategy(StrEnum):
    """澄清策略"""

    FIRST_PRINCIPLES = "first_principles"  # 第一性原理拆解
    VALUE_ASSESSMENT = "value_assessment"  # 产品价值评估
    SOCRATIC = "socratic"  # 苏格拉底追问
    SUFFICIENCY_FIRST = "sufficiency_first"  # 信息不足，先收集再路由


# ---------------------------------------------------------------------------
# 策略路由
# ---------------------------------------------------------------------------

ROUTE_KEYWORDS = {
    ClarificationType.NEW_DOMAIN: [
        "新业务", "新方向", "从零开始", "探索", "转型",
        "竞品都在做", "要不要跟", "全新", "新领域",
    ],
    ClarificationType.OPTIMIZATION: [
        "优化", "改进", "重构", "升级", "调整", "方案评审",
        "风险", "验证", "评估方案", "拷问",
    ],
}


def route_strategy(
    title: str,
    description: str,
    conversation_round: int,
) -> ClarificationStrategy:
    """根据需求信息自动路由到最佳澄清策略。

    路由逻辑:
    1. 对话轮次 < 2 且信息不足 → SUFFICIENCY_FIRST (先收集基本信息)
    2. 关键词匹配 NEW_DOMAIN → FIRST_PRINCIPLES
    3. 关键词匹配 OPTIMIZATION → SOCRATIC
    4. 其他 → VALUE_ASSESSMENT (最通用)
    """
    if conversation_round < 2:
        combined = f"{title} {description}"
        if len(combined.strip()) < 20:
            return ClarificationStrategy.SUFFICIENCY_FIRST

    combined = f"{title} {description}".lower()

    for keyword in ROUTE_KEYWORDS[ClarificationType.NEW_DOMAIN]:
        if keyword in combined:
            return ClarificationStrategy.FIRST_PRINCIPLES

    for keyword in ROUTE_KEYWORDS[ClarificationType.OPTIMIZATION]:
        if keyword in combined:
            return ClarificationStrategy.SOCRATIC

    return ClarificationStrategy.VALUE_ASSESSMENT


# ---------------------------------------------------------------------------
# 策略 Prompt 模板
# ---------------------------------------------------------------------------

FIRST_PRINCIPLES_PROMPT = """\
## 澄清策略: 第一性原理拆解

这是一个方向不明确的需求，需要从零重构问题。按以下思路引导用户:

**当前阶段**: {current_stage}

### 递进引导（逐步推进，每次只聚焦当前阶段）:

1. **原始问题** — "你最初想解决什么问题？这个想法背后隐含了哪些假设？"
2. **追问根因** — "为什么要做这个？解决了能得到什么？"（连续追问 3-4 层到核心目标）
3. **识别底层约束** — "有哪些物理/经济/人性规律是绕不过去的？手上有什么基本材料可以直接用？"
4. **重新定义问题** — 基于拆解，帮用户重新表述问题；区分硬约束和软约束（行业惯例可挑战）
5. **从零重构方案** — "基于底层真相，能组装出哪些可能的路径？"引导想出 3-5 个候选路径
6. **挑战行业假设** — "这个领域有哪些'大家都这么做'的惯例？它们还成立吗？"

### 关键原则:
- 不接受"因为竞品这么做"作为理由
- 每个假设都要追问"为什么可以这样默认？如果不成立会怎样？"
- 最终产出: 重新定义的问题 + 3-5 个候选方案 + 每个方案的成本与可行性"""

VALUE_ASSESSMENT_PROMPT = """\
## 澄清策略: 产品价值评估

这是一个有方向的功能需求，需要系统评估其价值和可行性。按以下思路引导用户:

**当前阶段**: {current_stage}

### 六维拆解（逐维度引导，每次只问当前维度）:

1. **目标用户** — "核心用户是谁？他们有什么共性？用户量级？"
   - 聚焦度自检: 用户群体是否收敛到可画像的程度？
2. **使用场景** — "用户在什么情境下会用到？触发条件是什么？"
   - 场景价值自检: 场景是否高频/高价值？
3. **核心痛点** — "当前用户怎么解决这个问题？痛在哪？"
   - 痛点强度自检: 不解决会怎样？有多急迫？
4. **现有方案** — "市面上已有的解法是什么？为什么不够好？"
   - 差异性自检: 我们的方案与现有方案的本质区别？
5. **核心方法** — "我们用什么独特方法解决？凭什么比现有方案好？"
   - 可行性自检: 技术上能实现吗？成本可控吗？
6. **预期价值** — "做完后用户行为会有什么改变？可量化吗？"
   - 可验证性自检: 上线后怎么知道成功了？

### 核心假设句式（六维完成后汇总）:
> 对于 [用户]，在 [场景] 下遇到 [痛点]，现有方案是 [现有方案]，
> 我们通过 [核心方法]，预期带来 [价值]。

### 决策建议:
- 六维都清晰 → 通过，可以开始产出需求规格
- 3+ 维模糊 → 需修正，继续追问
- 核心假设站不住 → 推翻，需重新定义问题（切换第一性原理）"""

SOCRATIC_PROMPT = """\
## 澄清策略: 苏格拉底追问

这是一个有具体方案需要验证的需求，用六层追问拷问其逻辑。按以下思路引导用户:

**当前阶段**: {current_stage}

### 六层追问（重点关注第二、六层，从表面到本质）:

1. **澄清概念** — "这个需求里的关键词分别指什么？哪些是事实、哪些是判断？"
   - 避免各说各话，统一语言
2. **探查假设**（最关键） — "这个需求背后默认了什么？为什么可以这样默认？如果不成立会怎样？"
   - 列出所有隐含假设，评估每个的脆弱度
3. **审视证据** — "支撑这个方案的逻辑链条是什么？从 A 到 B 必然成立吗？有反面证据吗？"
4. **替代观点** — "反对者会怎么说？有没有中间立场或更复杂的模型？"
5. **检验后果** — "如果按这个逻辑推演下去会怎样？有不可逆的风险吗？"
6. **反诘问题**（最容易被跳过但最重要） — "我们是否应该问一个更根本的问题？这个问题本身是否隐含了错误的预设？"

### 判定标准:
- 命题通过: 所有关键假设经受住了追问
- 需要修正: 部分假设脆弱但可修补
- 推翻: 核心假设不成立
- 需重新定义: 问题本身有错误预设（切换第一性原理）"""

SUFFICIENCY_FIRST_PROMPT = """\
## 澄清策略: 信息收集

当前信息不足以判断适合哪种深度分析方法。先收集基本信息:

请引导用户回答:
1. 这个需求主要想解决什么问题？
2. 目标用户是谁？
3. 有初步的解决方向吗？

收集到上述信息后，再决定用"第一性原理拆解"还是"产品价值评估"还是"苏格拉底追问"来深化。"""

STRATEGY_PROMPTS: dict[ClarificationStrategy, str] = {
    ClarificationStrategy.FIRST_PRINCIPLES: FIRST_PRINCIPLES_PROMPT,
    ClarificationStrategy.VALUE_ASSESSMENT: VALUE_ASSESSMENT_PROMPT,
    ClarificationStrategy.SOCRATIC: SOCRATIC_PROMPT,
    ClarificationStrategy.SUFFICIENCY_FIRST: SUFFICIENCY_FIRST_PROMPT,
}


# ---------------------------------------------------------------------------
# 阶段推进
# ---------------------------------------------------------------------------

STRATEGY_STAGES: dict[ClarificationStrategy, list[str]] = {
    ClarificationStrategy.FIRST_PRINCIPLES: [
        "原始问题与假设识别",
        "追问根因（连续3-4层）",
        "识别底层约束与可用资源",
        "重新定义问题",
        "从零重构候选方案",
        "挑战行业假设",
    ],
    ClarificationStrategy.VALUE_ASSESSMENT: [
        "目标用户画像",
        "使用场景识别",
        "核心痛点挖掘",
        "现有方案分析",
        "核心方法与差异性",
        "预期价值与验证方式",
    ],
    ClarificationStrategy.SOCRATIC: [
        "概念澄清与事实分离",
        "探查隐含假设",
        "审视证据与逻辑链",
        "替代观点",
        "检验后果",
        "反诘问题本身",
    ],
    ClarificationStrategy.SUFFICIENCY_FIRST: [
        "收集基本信息",
    ],
}


def get_current_stage(strategy: ClarificationStrategy, conversation_round: int) -> str:
    """根据对话轮次推算当前应处于的阶段。"""
    stages = STRATEGY_STAGES.get(strategy, [])
    if not stages:
        return "信息收集"
    # 每 2 轮对话推进一个阶段
    stage_idx = min(conversation_round // 2, len(stages) - 1)
    return stages[stage_idx]


def build_clarification_prompt(
    strategy: ClarificationStrategy,
    conversation_round: int,
) -> str:
    """构建当前策略 + 阶段的 prompt 注入内容。"""
    template = STRATEGY_PROMPTS.get(strategy, SUFFICIENCY_FIRST_PROMPT)
    current_stage = get_current_stage(strategy, conversation_round)
    return template.format(current_stage=current_stage)
