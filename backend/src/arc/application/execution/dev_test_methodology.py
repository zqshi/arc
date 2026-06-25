"""开发与测试方法论引擎 — 基于 obra/superpowers 改造。

来源: obra/superpowers 中的:
  - test-driven-development: RED-GREEN-REFACTOR 强制循环
  - verification-before-completion: 完成前必须验证
  - systematic-debugging: 4 阶段根因定位
  - writing-plans: 任务拆解为 2-5 分钟的原子步骤

职责:
  - 开发阶段: 注入 TDD 循环 + 增量实现策略
  - 测试阶段: AC 逐条验证 + 证据要求
  - 两个阶段共享: "声称完成前必须验证"原则
"""

from __future__ import annotations

import logging

from arc.application.execution.llm_review import default_llm_review

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 开发阶段方法论
# ---------------------------------------------------------------------------

DEVELOPMENT_METHODOLOGY_PROMPT = """\
## 开发方法论: TDD 循环 + 增量实现

**核心原则**: 声称完成前必须验证（verification-before-completion）

**当前阶段**: {current_stage}

### TDD 循环（每个功能点强制执行）

```
RED    → 写一个会失败的测试（明确预期行为）
GREEN  → 写最少代码让测试通过
REFACTOR → 在测试保护下重构
COMMIT → 测试全绿才提交
```

### 增量实现策略

将 implementation_plan 拆为**原子步骤**（每步 2-5 分钟可完成）:
1. 每步有明确的输入/输出/验证条件
2. 每步完成后运行测试确认不破坏已有功能
3. 步骤间保持独立——一步失败不影响其他步骤回滚

### 验证标准（声称"开发完成"前必须满足）

- [ ] 所有新增功能都有对应测试
- [ ] 测试全部通过（无 FAIL / ERROR）
- [ ] 无 lint 错误（如项目配置了 linter）
- [ ] 代码变更覆盖了 implementation_plan 中的所有步骤
- [ ] 没有 TODO/FIXME 标记的遗留问题

### 调试方法论（遇到测试不过时）

4 阶段根因定位（systematic-debugging）:
1. **复现** — 确认问题可稳定复现，记录复现步骤
2. **定位** — 二分法缩小范围，找到最小复现单元
3. **根因** — 不修表象，找到根本原因
4. **验证** — 修复后确认：原问题解决 + 无新问题引入

### 反模式（绝对避免）:
- ❌ 先写实现再补测试（顺序颠倒 = 测试沦为橡皮章）
- ❌ 一次性写完所有代码再测试（失败时无法定位问题）
- ❌ 测试通过但没有实际验证（mock 太多导致测试与现实脱节）
- ❌ "它在我本地能跑"（必须在干净环境验证）
"""


TESTING_METHODOLOGY_PROMPT = """\
## 测试方法论: AC 逐条验证 + 证据驱动

**核心原则**: 每个验收标准(AC)必须有可审计的 pass/fail 证据

**当前阶段**: {current_stage}

### AC 逐条验证流程

对照需求规格中的 `acceptance_criteria`，逐条执行:

```
对于每个 AC-N:
  1. 构造测试场景（匹配 AC 描述的 scenario）
  2. 执行操作步骤（匹配 AC 描述的 steps）
  3. 验证预期结果（匹配 AC 描述的 expected）
  4. 记录证据: pass/fail + 实际输出
```

### 证据标准

| pass 证据 | fail 证据 |
|-----------|-----------|
| 测试命令输出 (stdout) | 错误信息 + 堆栈 |
| 断言通过的日志 | 实际值 vs 预期值 |
| API 响应 200 + 正确 body | 状态码 + 错误 body |
| 截图/录屏（UI 相关） | 异常界面截图 |

### 测试覆盖度要求

- P0 验收标准: **100% 覆盖**，每条必须有 pass/fail
- P1 验收标准: **≥80% 覆盖**
- P2 验收标准: 尽力覆盖，未覆盖的标注原因

### 验证完成标准

- [ ] 所有 P0 AC 有 pass 证据
- [ ] 失败的 AC 有明确的 issue 描述 + severity + 修复建议
- [ ] coverage_summary 包含覆盖率数字
- [ ] 无"自述式"结论（每个 pass/fail 都有证据支撑）

### 反模式:
- ❌ "测试通过"但无测试命令输出（不可审计）
- ❌ 只测 happy path 不测边界/异常
- ❌ AC 未覆盖但标记为"通过"（跳过 ≠ 通过）
"""


# ---------------------------------------------------------------------------
# 阶段推进
# ---------------------------------------------------------------------------

DEVELOPMENT_STAGES = [
    "任务拆分 — 将 implementation_plan 拆为原子步骤",
    "TDD 第一轮 — 核心功能的 RED→GREEN→REFACTOR",
    "增量推进 — 逐步骤实现 + 持续验证",
    "收尾验证 — 全量测试 + lint + 覆盖度确认",
]

TESTING_STAGES = [
    "测试规划 — 逐条对照 AC 制定测试方案",
    "P0 验证 — 核心 AC 逐条执行 + 记录证据",
    "P1/P2 验证 — 次要 AC 覆盖",
    "汇总报告 — 覆盖率 + issues + 修复建议",
]


def get_development_prompt(conversation_round: int) -> str:
    """开发阶段方法论 prompt。"""
    stage_idx = min(conversation_round // 3, len(DEVELOPMENT_STAGES) - 1)
    return DEVELOPMENT_METHODOLOGY_PROMPT.format(current_stage=DEVELOPMENT_STAGES[stage_idx])


def get_testing_prompt(conversation_round: int) -> str:
    """测试阶段方法论 prompt。"""
    stage_idx = min(conversation_round // 2, len(TESTING_STAGES) - 1)
    return TESTING_METHODOLOGY_PROMPT.format(current_stage=TESTING_STAGES[stage_idx])


# ---------------------------------------------------------------------------
# 开发产出物校验
# ---------------------------------------------------------------------------

async def validate_development(content: dict, *, llm_review_fn=None) -> list[str]:
    """开发报告质量校验。

    测试结果失败检测采用 🟡结构预筛 + 🟢LLM确认 + 降级兜底:
    字面预筛命中 FAIL/ERROR 后, LLM 判断测试是否真失败(区分测试名/注释中
    的字样 vs 实际失败), LLM 异常回退字面匹配(原行为)。其余为纯结构校验。

    Args:
        llm_review_fn: 可注入 (prompt) -> dict, 用于测试; None 用 default_llm_review。
    """
    gaps = []

    test_results = content.get("test_results", "")
    if isinstance(test_results, str):
        if "FAIL" in test_results.upper() or "ERROR" in test_results.upper():
            # 🟡预筛命中 → 🟢LLM确认是否真失败
            gaps.extend(await _check_test_failure(test_results, llm_review_fn))
        if not test_results.strip():
            gaps.append("test_results 为空，缺少测试验证")

    code_changes = content.get("code_changes", [])
    if isinstance(code_changes, list) and len(code_changes) == 0:
        gaps.append("code_changes 为空，无代码变更记录")

    return gaps


_TEST_FAILURE_REVIEW_PROMPT = """\
判断以下测试命令输出是否表示测试真正失败(而非测试名/注释中恰好出现 FAIL/ERROR 字样)。

测试输出:
{output}

输出 JSON 契约:
{{"failed": true}}

failed=true: 测试真正失败(有 failed test / 断言失败 / 异常退出);
failed=false: 测试实际通过(FAIL/ERROR 仅出现在测试名或描述中)。"""


async def _check_test_failure(test_results: str, llm_review_fn) -> list[str]:
    """🟡预筛已命中 FAIL/ERROR, 🟢LLM确认是否真失败, 返回 gaps。

    降级: LLM 异常/解析失败 → 回退字面匹配(报 gap, 原行为)。
    """
    try:
        prompt = _TEST_FAILURE_REVIEW_PROMPT.format(output=test_results[:4000])
        if llm_review_fn is not None:
            data = await llm_review_fn(prompt)
        else:
            data = await default_llm_review(prompt)
        failed = bool(data.get("failed", True)) if isinstance(data, dict) else True
        return ["测试结果中存在 FAIL/ERROR，开发未完成"] if failed else []
    except Exception as exc:
        logger.warning("测试失败 LLM 校验降级, 回退字面匹配: %s", exc)
        return ["测试结果中存在 FAIL/ERROR，开发未完成"]


def validate_testing(content: dict, prior_requirement: dict | None = None) -> list[str]:
    """测试报告质量校验 — 含 AC 逐条覆盖度检查。"""
    gaps = []

    verifications = content.get("criteria_verification", [])
    if not verifications:
        gaps.append("criteria_verification 为空，无验证记录")
        return gaps

    # 检查是否有证据
    for v in verifications:
        if not isinstance(v, dict):
            continue
        status = v.get("status", "")
        evidence = v.get("evidence", "")
        if status == "pass" and not evidence:
            criteria = v.get("criteria", "未知")[:30]
            gaps.append(f"验收标准「{criteria}」标记 pass 但无证据")

    # AC 覆盖度检查
    if prior_requirement:
        acs = prior_requirement.get("acceptance_criteria", [])
        p0_acs = [ac for ac in acs if isinstance(ac, dict) and ac.get("priority") == "P0"]
        if p0_acs and len(verifications) < len(p0_acs):
            gaps.append(
                f"P0 验收标准 {len(p0_acs)} 条，"
                f"但 criteria_verification 只有 {len(verifications)} 条"
            )

    return gaps
