# Prompt 升级路线图 — 规则执行式 → 意图驱动

> 状态: v5.10(#1-6)已归档, v6.0 #7 sufficiency已完成(产出前门禁), v6.3 #8 drift_detector/#9 error_loop_detector已完成(混合: 结构预筛+LLM确认), 进度 9/14
> 关联: backlog.md v6.3.0 前置 / memory [AI Interaction Philosophy]

## 背景

Arc 的核心交互哲学是**意图驱动 + Agent 自主推理**: 给 LLM 目标 + 输出契约 + 上下文, 让模型自主判断, 反对"规则执行式"(if/else 硬规则、checklist 死板校验、字面匹配)。

但审计发现实现存在"买椟还珠"——**意图驱动能力建好却没接线, 或曾实现后被删除回归**, 实际跑的是劣质规则执行版。本路线图梳理全部 14 处, 分优先级、分版本升级。

判定标准:
- 🟢 意图驱动: prompt 给目标 + 输出契约, LLM 自主推理
- 🟡 混合: 硬规则做快速预筛 + LLM 做质量判断
- 🔴 规则执行式: 纯字面匹配/计数/正则 (反模式, 待升级)

---

## 已完成 (v5.10 #1-6 + v6.0 #7)

| # | 位置 | 升级内容 | 意图驱动度 |
|---|------|---------|-----------|
| 1 | `execution/artifact_extractor.py:77-81` | 门禁从"仅记录不阻断"改为**按 constraint 分级阻断** (复用 gate.py 4 层) | 🟢→🟢 |
| 2 | `execution/conversation_gate.py` (新) + `gate_threshold.py` (新) | 对话模式门禁接线, `GateProfile` 注册表分级 (free≥5/moderate≥6/strict≥7) | 🟢 |
| 3 | `planning/entity.py` is_quality_complete | 完成判定从"状态标志"升级为"门禁通过双重校验" | 🟢 |
| 4 | `pipeline/hooks.py` trigger_deployment | 部署从"三重静默 skip"改为 `check_build_ready` **硬门禁** | 🟢 |
| 5 | `conversation/service.py:_build_clarification_prompt` | 澄清从"固定6层苏格拉底"切到 **`clarification_strategy` 三策略路由** (按需求类型动态选方法论) | 🟢 |
| 6 | `execution/execution_engine.py` run_autopilot | auto_advance 从"盲目推进"改为**门禁卡点反馈重试** + max_gate_retries 截断 | 🟡 |
| 7 | `execution/sufficiency_gate.py`(新) + `artifact/service.py` confirm + `context/providers/sufficiency.py` | sufficiency 接线为 requirement_spec **产出门禁**(产出前判断), 非每轮注入; 职责分离: 轮次管引导, LLM 管质量判断; 降级放行 | 🟢 |
| 8 | `execution/drift_detector.py` | Jaccard 关键词重叠度判漂移 → **混合**: 🟡Jaccard预筛(重复循环→SEVERE, >=0.50→NONE, 控成本) + 🟢LLM确认(serves_goal+置信度精确分级); 降级Jaccard阈值 | 🟡 |
| 9 | `execution/error_loop_detector.py` | LCS 字符串相似度判循环 → **混合**: 🟡LCS预筛(签名周期重复→True) + 🟢LLM确认(窗口满+有错误+LCS判否时判"换工具犯同类错"); 降级LCS; 提取公共 llm_review.py 消除重复 | 🟡 |

---

## 待升级清单 (剩余 7 处)

| # | 位置 | 现状(🔴) | 目标(🟢/🟡) | 优先级 | 版本 |
|---|------|---------|------------|--------|------|
| 10 | `execution/tool_loop.py:312` | 死板 3 次重试 + sleep | LLM 诊断错误类型(超时/权限/逻辑) → 决策(重试/换工具/放弃) | P1 | v6.1 |
| 11 | `execution/architecture_methodology.py:178` | 正则判事件名"过去时态" | LLM DDD 合规判断 (或保留结构校验为 🟡 预筛) | P2 | v6.2 |
| 12 | `execution/dev_test_methodology.py:156` | `"FAIL" in text.upper()` 字面匹配 | LLM 解析测试结果语义 | P2 | v6.2 |
| 13 | `execution/constraint_policy.py:202` | `route_strategy("","",round)` 空参数(主路径已修, 此处为 pipeline strict 方法论残留) | 传入真实 title/description 或移除该调用点 | P2 | v6.2 |
| 14 | `context/prompt_builder.py:140` `_infer_phase` | 按 artifact 完成顺序硬编码推断阶段 | 结合门禁结果 + 剩余工作量, LLM 推理推进/回退 | P2 | v6.2 |

---

## #7 sufficiency 接线设计 (P0, ✅ 已决策并实现: 产出前门禁)

> **决策结果 (用户确认, 2026-06-24)**: 采用**方案 B 产出前门禁**, 非 plan 原推荐的 A+B。
> 理由: 每轮注入"引导用户多说"不需要 LLM(轮次计数够用); 三维评估的真正价值是"产出前语义质量判断", 是门禁场景而非每轮注入。引入缓存复杂度高、用户补信息即失效, 收益不明。
> 实现: `sufficiency_gate.py` 接入 `ArtifactService.confirm()` 的 requirement_spec 确认前门禁; provider 保留 <2 轮粗引导。详见 [v6.0.0-current.md T7](versions/v6.0.0-current.md)。

**核心矛盾**: `INPUT_SUFFICIENCY_PROMPT` 的 LLM 三维评估(target_users/core_problem/feature_direction)远优于轮次计数, 但 `SufficiencyHintProvider.provide()` 是**每轮注入上下文**——简单接线会让每轮对话多一次 LLM 调用, 成本不可接受。

**~~推荐方案: 轮次预筛 + 节点性 LLM 评估(带缓存)~~** (未采纳 — 缓存复杂度高、用户补信息即失效)

```
provider.provide():
  1. 快速预筛 (零成本): user_rounds < 阈值 → 注入轮次提示 (现状保留)
  2. 达阈值时, 查缓存:
     - 缓存键: todo_id + conversation 指纹(最近 2 轮内容 hash)
     - 命中 → 用缓存的 sufficiency 评估注入
     - 未命中 → 调 INPUT_SUFFICIENCY_PROMPT, 结果写缓存 + artifact metadata
  3. sufficient=true → 不再注入 sufficiency 提示 (信息够了)
```

- **缓存粒度**: 按 conversation 内容指纹, 避免每轮重算; 状态变化(用户补充信息)才重评估
- **降级**: LLM 不可用 → 回退轮次计数 (现状), 不阻断
- **成本**: 典型对话从"每轮 0 次"变"每 2-3 轮 1 次", 可接受

**✅ 采纳方案(替代方案 B)**: sufficiency 只在**产出 requirement_spec 前**作为门禁调一次 (复用 conversation_gate 机制), 不做每轮注入。更省成本, 职责分离: 轮次管引导, LLM 管质量判断。

**~~决策点(待用户确认)~~**: ~~渐进注入(方案A) vs 产出前门禁(方案B) vs 两者结合~~ → **已决策: 方案 B 产出前门禁**。

---

## 版本推进计划

| 版本 | 范围 | 依赖 |
|------|------|------|
| **v5.10** ✅ | #1-6 自由模式门禁 + 部署 + 澄清双轨 | 无 |
| **v6.0** | #7 sufficiency 接线 ✅done (产出前门禁) + 项目类型推理 + ConstraintPolicy 死配置清理 | - |
| **v6.1** | #8-10 drift/error_loop/tool_loop 语义化 (执行链路稳定性) | 无 |
| **v6.2** | #11-14 methodology/prompt_builder 残留规则 (质量精细度) | 无 |

**v6.3.0 解除阻塞**: 本路线图落地后, v6.3.0(项目治理规范传递)的前置满足——Arc 自身规范意图驱动化已稳定, 可安全抽象成模板分发给新项目, 不会把过渡期反模式锁死。

---

## 设计原则 (升级时遵守)

1. **复用 > 新建**: 升级不是另起一套, 是把规则执行版的判断逻辑替换为 LLM prompt + 输出契约, 复用现有数据流
2. **混合优先**: 纯 LLM 有成本/延迟/不稳定问题, 纯规则有语义缺失。结构校验做🟡快速预筛(省 LLM), LLM 做质量判断, 是多数场景最优解
3. **降级兜底**: LLM 失败/不可用时回退规则版, 不阻断主流程
4. **意图驱动 prompt 纪律**: prompt 只给目标 + 输出契约 + 上下文, 不给步骤/规则/模板 (见 memory [AI Interaction Philosophy])
5. **门禁分级**: 不同 constraint 用 GateProfile 注册表分级, 不在 service 写 if 分支
