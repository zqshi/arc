# arc 架构升级提案（对照 ClawMate）

> 状态: **提案 / 暂不落地** (2026-07-01)。沉淀分析供后续有需要时取用。
> 参考文档: ks-clawmate `docs/agent-contract-design.md` (Agent/ToolPlan/RuntimeBootstrapSnapshot 契约) + `docs/clawmate-external-tools-workflow.html` (外部工具受控调用数据面)。
> 适用前提: 本文是**架构思路**, 不是版本计划。任何落地都需单独立版本 (current.md) 并 TDD。

---

## 1. 背景

对照 ClawMate (多租户多服务 Agent 平台) 的两份设计文档, 评估 arc 的架构是否有升级空间。结论先行: **两者是不同物种**, 多数 ClawMate 模式对 arc 是过度设计, 但有 2-3 个契约/治理模式契合 arc 已有的治理哲学 (charter/gate), 值得借鉴。

### 1.1 核心结论

- **ClawMate**: 多租户、多服务、沙箱化的 Agent 托管平台 (agent-center / tool-registry / runtime-conductor / runtime-gateway / credential-service 五服务 + Higress 数据面 + cmcli runtime)。
- **arc**: 单进程、单用户的产品研发工作台 (FastAPI + React, 本地/单租户迭代, charter + pipeline + gate 全链路治理)。
- 照搬 ClawMate 多服务架构 = 对 arc **严重过度设计**。真正的升级空间在 **把 arc 自己的治理哲学连贯延伸到目前放任的工具层**。

---

## 2. arc 现状对照

核实后的 arc 实际形态 (非推断):

| 维度 | ClawMate | arc 现状 | 差距性质 |
|------|----------|----------|----------|
| 工具调用 | 受控网关路径 `/rt/mcp/x` + 鉴权 + 凭据注入 + 审计 | adapter CLI 直连 MCP URL (`adapters/claude_code.py` 写 `--mcp-config` 临时文件, CLI 自连 MCP server) | **治理真空** (真问题) |
| 工具契约 | ToolPlan: provider→tools + auth(action+subjects) + risk + target | `Capability`(loose config) + `ToolSpec`(name/params/server_ref) | 缺 auth/risk/audit/target 语义 |
| 控制面/执行面 | AgentDefinition 声明 → 编译 → RuntimeBootstrapSnapshot 不可变快照 | pipeline_config/process_config 是**活 dict**, 实时消费; 仅 domain_model 有版本历史 | arc 故意可变 (迭代工作台特性) |
| 凭据 | DB 托管 + 网关单点注入, 快照只含 ref | DB 加密(Fernet) + application 解析注入(`adapter_pool`/`resolve_from_project`) | arc 基本已有此模式 |
| Skill | 版本化包 (packageAssetId + checksum, asset-service 交付) | `capability/skill_loader.py` loose 加载 | 弱版本化 |
| 部署形态 | 多服务 + Higress + 插件 + sandbox | 单进程 FastAPI | 不同规模, 不该对齐 |
| 审计 | runtime-gateway proxy + tool call log | 无工具调用审计 (CLI 自管, arc 不回看) | 工具行为不可观测 |

关键事实: arc 的 agent adapter 把工具调用**完全外包给 CLI** —— claude_code/cursor 拿到 `--mcp-config` 后自己直连 MCP server URL, arc 既不知 Agent 调了什么工具, 也无 risk 分级 / allowlist / auth 语义 / 审计。grep `risk|side_effect|audit|allowlist|permission` 在 capability 域**全空**。

---

## 3. 不该学 (过度设计)

以下 ClawMate 模式解决的是 arc **没有的问题**, 强加只增负担:

- **拆微服务** (agent-center/tool-registry/runtime-conductor/runtime-gateway/credential-service 各自独立部署): arc 单进程跑得好好的, 拆了只增运维/网络/一致性负担, 单用户零收益。
- **Higress + clawmate-auth 插件 + runtime-gateway-upstream 数据面**: 为多租户沙箱 + 不受信 Agent 设计。arc 没有不可信 Agent 隔离需求。
- **TS/Go 多语言 `libs/contracts`**: arc 是 Python 后端 + TS 前端, 契约已通过 `types/api.ts` + Pydantic schema 共享, 不存在 ClawMate 那种 5 服务跨语言复制问题。
- **agentRevisionId 发布流 + RuntimeBootstrapSnapshot 作为不可变发布制品**: arc 配置故意 live/mutable (用户迭代调参是核心交互), 强加发布版次破坏工作台体验。

---

## 4. 值得学 (按 ROI 排序)

### ① ToolPlan 式工具治理契约 — 契合 arc 治理哲学【高 ROI】

**真问题**: arc 在交付物层门禁森严 (gate/methodology/cross-consistency), 在工具调用层却完全放任 —— 治理断层。charter 治理了"产出什么", 没治理"用什么手段产出"。

**借鉴方式 (不照搬网关)**:
- 给 arc 加一个**进程内 ToolPlan 概念**: 由 project capabilities + charter 编译出"本次运行允许的工具集 + 每个工具的 risk/side-effect/target/auth-need"。
- adapter 启动时不只丢 `mcp_config`, 还生成 ToolPlan 清单; CLI 工具调用日志回传 arc 审计/经验沉淀。
- 把 arc 治理从"交付物门禁"延伸到"工具行为", **不动部署形态** (ToolPlan 是内存契约, 不是服务)。

**适配取舍**: ClawMate 的"网关强执行 (请求必经网关)"在 arc 的 CLI-subprocess 模型下成本高 (要代理 MCP)。arc 第一版走 **"manifest + 事后审计"** 而非"网关拦截", 等工具生态大了再考虑代理。

### ② 运行起手快照 (RuntimeBootstrapSnapshot 思路) — 经验沉淀刚需【中 ROI】

**真问题**: arc 重度依赖 experience 沉淀 (extract_experience / experience_card / domain_model_history), 但一次 Agent 运行的**完整起手上下文** (当时 config 快照 + 工具集 + model + charter 版本 + 凭据 ref) 未被固化成不可变制品。经验卡难精确复现/审计。

**借鉴方式**: agent 运行**起手时** snapshot 一份带 `schemaVersion` 的不可变 manifest。**不改 config 的 live 可变性** (config 跨运行仍可调), 只 per-run 固化。比 ClawMate 的"发布期 AgentRevision 快照"更轻 —— arc 不需要发布流, 只需 per-run 起手快照。

### ③ 凭据单点注入边界 — 卫生项【低 ROI, arc 大半已有】

arc 已有 DB 加密 + `adapter_pool`/`resolve_from_project` 单点解析。ClawMate 的"凭据永不入 ToolPlan/snapshot, 只入 ref"是好的卫生约束。若 arc 引入 ① ToolPlan 或 ② 运行快照, **必须从一开始就让它们只持 credential ref** (沿用现有 `llm_provider_id` 指针模式, 别开倒车回明文)。这是 ①② 的**伴随约束**, 非独立任务。

### ④ 外部 MCP 受控路径 — 看 arc 工具路线图【条件性】

arc 的 `mcp_client.py` 直连外部 MCP。若未来集成大量付费/有副作用外部服务 (Tavily 类), 需受控 chokepoint (risk-gate + 凭据注入 + 审计)。当前 arc 外部工具面很小, **路线图驱动, 不急着建**。

---

## 5. 核心洞察

ClawMate 架构的真正优点不是"微服务拆分", 而是 **"目录声明"与"调用执行"之间有一道受控边界"**。

arc **在管线层已有这道边界** (charter 声明 → gate 强制 → execution engine 执行), 却**在工具层没有** (工具调用全外包给 CLI, 无治理)。

**最高杠杆升级**: 不是抄 ClawMate 的服务, 而是 **把 arc 自己的治理哲学 (charter/gate) 连贯延伸到工具调用层** —— 用一个进程内 ToolPlan 把工具纳入治理。既契合 arc 产品身份 (治理型工作台), 又不背单进程规模现实。

---

## 6. 候选落地草图 (DDD 分层, 未落地)

以下为 ①② 的 DDD 落地草图, 供未来取用。**未实现, 仅设计。**

### 6.1 候选 ① ToolPlan 工具治理契约

```
domain/capability/value_objects.py (扩展)
  ToolRisk            # 值对象: level(low/med/high) + side_effect(read/write/exec)
  ToolTarget          # 值对象: protocol(mcp/http) + path/server/toolName + gateway_route_id?
  ToolPlanAuth        # 值对象: action(none/forward_agent/inject_credential/...) + subjects
  ToolEntry           # alias + canonical_name + input_schema + target + risk + auth
  ToolPlan            # 值对象: schemaVersion + providers[]→tools[] (provider 分层 + 默认 auth)

domain/capability/entity.py
  Capability          # 现有; config 收口为持 ToolTarget/risk 等结构化字段 (非 loose dict)

application/capability/tool_plan_compiler.py (新)
  compile_tool_plan(project, charter, capabilities) -> ToolPlan
  # 从 project 绑定的 capabilities + charter 约束编译出 per-run ToolPlan
  # charter 可声明禁用高风险工具 (write/exec), 编译期过滤

application/agent/adapters/*.py (改造)
  # adapter 启动时收 ToolPlan (非裸 mcp_servers), 生成 mcp_config + ToolPlan 清单
  # 工具调用日志 (若 CLI 可回传) 写 tool_call_log

infrastructure/repositories/tool_call_log.py (新)
  # 审计: 记录 agent run 的工具调用 (alias/args/result 摘要/risk), 供 experience 沉淀

interface/routes/mcp.py / agent.py
  # 可选: 暴露 ToolPlan 给前端展示"本次允许的工具集"
```

**关键约束**: ToolPlan 只持 credential ref (如 `llm_provider_id`), 不持明文 (同 ③)。

**第一版取舍**: "manifest + 事后审计", 不代理 MCP 调用。CLI 直连 MCP 不变, 但 arc 有了可观测/可治理的工具清单 + 日志。

### 6.2 候选 ② 运行起手快照 (RuntimeRunManifest)

```
domain/agent/value_objects.py (扩展)
  RuntimeRunManifest   # 值对象: schemaVersion + run_id + 起手时刻固化
                       #   - config 快照 (pipeline_config/process_config/conversation_config 当时值)
                       #   - ToolPlan ref (若 ① 已落地) 或 capabilities 快照
                       #   - model (provider/model/parameters 当时值, 仅 ref 不含明文)
                       #   - charter 版本 (template_version + 内容 hash)
  # 不可变; 一次 agent run 一份

application/agent/session_manager.py (改造)
  # start_session 时编译 RuntimeRunManifest, 关联到 AgentSession

domain/experience/... (扩展)
  # experience_card 关联 RuntimeRunManifest, 经验卡可复现/审计当时上下文

infrastructure/repositories/run_manifest.py (新)
  # 持久化 manifest (JSONB), 按 run_id 查
```

**与 ① 的关系**: ② 的工具集字段, 若 ① 已落地则引用 ToolPlan; 否则退化为 capabilities 快照。建议先 ① 后 ② (② 依赖 ① 的工具契约更完整)。

---

## 7. 决策与触发条件

**当前决策 (2026-07-01): 暂不落地。** 理由:
- ① 的痛感取决于 arc 是否接入更多工具生态。当前 adapter 主要是 claude_code/cursor CLI + 少量 MCP, 治理真空不致命。
- ② 是 experience 复现的刚需, 但可与未来 experience 链路增强版本合并设计, 不必单独立。

**触发条件 (满足任一则考虑启动)**:
1. arc 接入 **3+ 个外部 MCP / 付费工具** → ① ToolPlan 治理 + ④ 受控路径的痛感显化。
2. experience 卡需要**精确复现历史 agent 运行** (用户反馈/审计需求) → ② 运行起手快照。
3. 出现**工具误用/越权**事故 (Agent 调了不该调的工具) → ① 治理刚需。
4. 多租户/团队协作列入路线图 → 整体重估 (可能需要 ③ 凭据边界 + 隔离)。

**启动姿势**: 先做 ① 地基 —— 给 `ToolSpec`/`Capability` 补 `risk/side-effect/target/auth-need` 结构化元数据 (domain 值对象, 零 infra), 让"工具"成为一等可治理概念。独立可交付, 不动调用路径。

---

## 8. 参考映射

| ClawMate 概念 | arc 对应/启示 | 是否借鉴 |
|---------------|--------------|---------|
| AgentDefinition (控制面声明) | arc 的 Project + charter + capabilities 已是声明面 | 不需新概念, 已有 |
| ToolPlan (工具执行快照) | arc 无 → 候选 ① | ✅ 借鉴契约语义 (非网关) |
| RuntimeBootstrapSnapshot (执行面材料) | arc 无 per-run 不可变快照 → 候选 ② | ✅ 借鉴 per-run 思路 (非发布流) |
| tool-registry / runtime-gateway / credential-service (多服务) | arc 单进程, adapter_pool + resolve_from_project 已是单点 | ❌ 过度设计 |
| Higress + clawmate-auth (数据面网关) | arc 无多租户沙箱需求 | ❌ 过度设计 |
| cmcli (runtime 工具调用) | arc 的 adapter CLI 自管工具 | △ 仅借鉴"工具清单 + 审计"思路 |
| schemaVersion 不可变快照 | arc 仅 domain_model_history 有版本 | ✅ 借鉴 schemaVersion 约束 |
| 凭据只入 ref 不入快照 | arc 已有 (llm_provider_id 指针 + Fernet) | ✅ 维持, 作为 ①② 伴随约束 |
| 版本化 skill 包 (checksum) | arc skill_loader loose | △ 弱借鉴, 优先级低 |
