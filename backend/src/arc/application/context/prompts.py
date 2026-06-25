"""对话驱动执行模式的系统提示词和产出物定义。

设计哲学：意图驱动，Agent 自主推理。
- prompt 只给目标 + 能力声明 + 上下文
- Agent 自主决定推进路径、产出时机、分析深度
- 质量通过输出接口契约 + 后置验证保障，不通过前置规则约束

注: ARTIFACT_SCHEMAS 已拆到 artifact_schemas.py (v5.8.0), 此处 re-export 保持兼容。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arc.application.context.artifact_schemas import ARTIFACT_SCHEMAS
from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType

if TYPE_CHECKING:
    from arc.domain.project.value_objects import ProjectType

# re-export 供 deliverable provider 等引用
__all__ = [
    "ARTIFACT_SCHEMAS",
    "ARTIFACT_TYPE_MARKERS",
    "ARTIFACT_LABELS",
    "CONVERSATION_MODE_SYSTEM_PROMPT",
    "AUTOPILOT_SECTION",
    "DELIVERABLE_CHECKLIST_TEMPLATE",
    "build_deliverable_checklist",
    "build_ddd_tdd_section",
    "PROTOTYPE_ENGINEERING_PROMPT",
    "PROTOTYPE_BUILD_GUIDES",
    "get_prototype_guide",
]

ARTIFACT_TYPE_MARKERS: dict[str, ArtifactType] = {
    "requirement_spec": ArtifactType.REQUIREMENT_SPEC,
    "interaction_design": ArtifactType.INTERACTION_DESIGN,
    "ui_spec": ArtifactType.UI_SPEC,
    "prototype": ArtifactType.PROTOTYPE,
    "tech_architecture": ArtifactType.TECH_ARCHITECTURE,
    "dev_report": ArtifactType.DEV_REPORT,
    "test_report": ArtifactType.TEST_REPORT,
    "deploy_report": ArtifactType.DEPLOY_REPORT,
    "experience_card": ArtifactType.EXPERIENCE_CARD,
    # Legacy
    "ui_design": ArtifactType.UI_DESIGN,
}

DELIVERABLE_CHECKLIST_TEMPLATE = """## 交付物清单
{checklist}

当你判断某个交付物可以产出时，使用以下格式：

[DELIVERABLE:{artifact_type}]
```json
{{结构化内容}}
```

系统会自动解析归档。用户可在侧边面板查看已归档产出物。"""


def build_deliverable_checklist(required: list[str], completed: list[str]) -> str:
    lines = []
    for atype in required:
        label = ARTIFACT_LABELS.get(ArtifactType(atype), atype)
        marker = "x" if atype in completed else " "
        lines.append(f"- [{marker}] {label}")
    return "\n".join(lines)


CONVERSATION_MODE_SYSTEM_PROMPT = """你正在帮用户完成「{title}」。

目标：作为搭档，把这个需求从想法推进到可交付的成果。你自主判断需要做什么、什么时候做、怎么做。

{deliverable_section}

{methodology_section}

{project_context}

{experience_context}

{sufficiency_hint}

## 当前任务
标题: {title}
描述: {description}

## 已完成的交付物
{completed_artifacts}"""


AUTOPILOT_SECTION = """## 自驾模式
你可以自主推进所有交付物，无需等待确认。只有在遇到真正无法独立决策的分歧点时
才暂停（输出 [NEEDS_INPUT]）。"""


# ---------------------------------------------------------------------------
# 交付物 JSON Schema（输出接口契约 — 不是规则，是让代码能解析的格式定义）
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# 领域模型上下文注入（只提供事实，不提供指令）
# ---------------------------------------------------------------------------


def build_ddd_tdd_section(domain_model: dict) -> str:
    """将项目领域模型作为上下文注入，供 Agent 自行判断如何使用。"""
    aggregates = domain_model.get("aggregates", [])
    relations = domain_model.get("relations", [])
    subdomains = domain_model.get("subdomains", [])
    contexts = domain_model.get("contexts", [])
    aggregate_relations = domain_model.get("aggregate_relations", [])

    if len(aggregates) < 2 and not subdomains:
        return ""

    # 模型元信息 — 版本和来源
    version = domain_model.get("version", "unknown")
    source = domain_model.get("source", "artifact_extraction")
    updated_at = domain_model.get("updated_at", "")

    lines = [
        f"## 项目领域模型（{len(aggregates)} 聚合, {len(subdomains)} 子域, "
        f"{len(contexts)} 上下文 | v{version}, 来源: {source}）"
    ]
    if updated_at:
        lines.append(f"*最后更新: {updated_at}*\n")

    if subdomains:
        lines.append("\n### 子域")
        for sd in subdomains:
            lines.append(
                f"- {sd.get('name', '')} ({sd.get('type', '')}): "
                f"{sd.get('description', '')}"
            )

    if contexts:
        lines.append("\n### 限界上下文")
        for ctx in contexts:
            line = f"- {ctx.get('name', '')}"
            if ctx.get("subdomain"):
                line += f" → {ctx['subdomain']}"
            if ctx.get("description"):
                line += f": {ctx['description']}"
            lines.append(line)

    if relations:
        lines.append("\n### 上下文关系")
        for rel in relations:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    if aggregates:
        lines.append("\n### 聚合")
        for agg in aggregates[:20]:
            name = agg.get("name", "")
            ctx = agg.get("context", "")
            parts = []
            if agg.get("entities"):
                parts.append(f"实体: {', '.join(agg['entities'][:5])}")
            if agg.get("value_objects"):
                parts.append(f"值对象: {', '.join(agg['value_objects'][:5])}")
            if agg.get("methods"):
                parts.append(f"方法: {', '.join(agg['methods'][:5])}")
            detail = "; ".join(parts) if parts else ""
            line = f"- **{name}**"
            if ctx:
                line += f" ({ctx})"
            if detail:
                line += f" — {detail}"
            lines.append(line)

    if aggregate_relations:
        lines.append("\n### 聚合关系")
        for rel in aggregate_relations[:15]:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    # 附加参考模式——Agent 根据项目实际情况自行选用
    lines.append("\n### 可参考的架构模式")
    lines.append(_REFERENCE_PATTERNS)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 参考模式库 — 作为上下文提供，Agent 自行判断适用性
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 原型工程化指导 — 告诉 AI 生成真实前端工程而非 HTML 片段
# ---------------------------------------------------------------------------

PROTOTYPE_ENGINEERING_PROMPT = """\
## 原型工程要求

当需要产出原型时，你需要使用 write_file 工具在项目目录下创建一个
**完整的前端工程**（不是 HTML 片段）。

### 目录结构

```
prototype/
├── package.json          # vite + react + react-router-dom + tailwindcss + zustand
├── vite.config.ts        # base: './' (相对路径，S3兼容)
├── tailwind.config.js
├── postcss.config.js
├── index.html            # 入口 HTML
├── src/
│   ├── main.tsx          # createRoot + HashRouter 挂载
│   ├── App.tsx           # 路由表 + 全局 Layout
│   ├── store.ts          # Zustand 状态 (用户、主题、Mock数据)
│   ├── pages/            # 每个路由一个页面组件
│   │   ├── Home.tsx
│   │   ├── Login.tsx
│   │   └── ...
│   ├── components/       # 共享组件 (Header, Sidebar, Modal, Toast)
│   │   ├── Layout.tsx
│   │   └── ...
│   └── styles/
│       └── index.css     # @tailwind base/components/utilities
```

### 关键约束

1. **HashRouter** — 使用 `createHashRouter`，S3 静态托管无需服务端路由
2. **共享 Layout** — Header/Sidebar/Footer 在 Layout 组件中，页面切换只替换内容区
3. **真实数据流** — 用 Zustand store 存 Mock 数据，列表→详情、表单→提交→反馈 全部可交互
4. **交互真实** — 按钮有 loading/disabled 状态、表单有即时校验、Toast 通知、Modal 确认
5. **状态持久** — 登录后导航栏变化、列表操作后数据更新，跨页面状态一致
6. **构建命令** — 完成所有文件后执行: `cd prototype && npm install && npm run build`
7. **Vite base** — vite.config.ts 中设置 `base: './'`（部署到 S3 子路径时路径正确）

### 产出格式

文件创建并构建成功后，输出 [DELIVERABLE:prototype] 包含工程清单 JSON（不是 HTML）:
```json
{
  "project_dir": "prototype",
  "tech_stack": "vite-react-tailwind",
  "routes": [{"path": "/", "name": "首页", "component": "src/pages/Home.tsx"}, ...],
  "shared_state": ["user", "currentProject", ...],
  "build_status": "success",
  "build_command": "npm run build",
  "artifact_path": "dist"
}
```

### 设计原则

- 像做真实产品一样做原型：用户拿到这个 URL 应该能体验到完整的产品交互
- 视觉用 Tailwind 实现，深色主题为主，风格现代简洁
- 移动端响应式（至少不崩溃）
- 组件粒度合理：不要把一个页面写 500 行，拆子组件
"""


BINARY_APP_BUILD_GUIDE = """\
## 原生客户端构建要求 (project_type=binary_app)

你的目标是产出可在容器沙箱内构建为原生客户端的工程，产物落 src-tauri/target/release/bundle。
默认框架 Tauri (Rust + WebView)，跨平台 web 资源复用前端工程。

### 你需要达成的状态

一个可被 `cargo tauri build` 成功构建的 Tauri 工程，产出**容器可构建目标**：
- linux 二进制 (.AppImage / deb)  ← v6.0 波次1 (本阶段聚焦)
- web 资源 (复用 static_site 的 dist)  ← 波次2 (镜像就绪后激活)
- android .apk (Capacitor)  ← 波次3 (镜像就绪后激活)

> 当前阶段(波次1)聚焦 linux bundle; web/apk 在后续波次镜像就绪后激活。
> 不在范围: macOS .dmg / Windows .exe 需原生 OS，容器化沙箱无法构建，推后到原生 runner/CI matrix。

### 工程结构

```
prototype/
├── package.json          # 前端 web 资源构建 (vite + react + tailwind)
├── src/                  # 前端源码 (与 static_site 同)
└── src-tauri/
    ├── Cargo.toml        # tauri 依赖
    ├── tauri.conf.json   # 应用元数据 + bundle targets (聚焦 deb/AppImage/apk)
    ├── src/main.rs       # tauri 入口
    └── icons/            # 应用图标
```

### 关键约束

- 构建在 arc/tauri-builder:linux 镜像内执行 (Rust+Node+webkit2gtk+tauri-cli,
  见 sandbox/images/), 无需宿主装工具链
- build_target=tauri_linux 时 tauri.conf.json 的 bundle.targets 配
  ["deb","appimage"] (波次1 唯一激活目标), 不配 dmg/msi/apk
- 前端 web 资源 build_command 与 static_site 一致 (npm run build → dist)，tauri 引用此 dist
- 构建/签名/分发分离：本阶段只保证构建产物落 bundle 目录；签名在 v6.1 (凭证可配)、分发在 v6.2
- Android 构建若用 Capacitor (波次3)，需配 capacitor.config.ts + android/ 平台目录

### 设计原则

- 复用前端工程：web 资源与 static_site 共用 src/，避免重复实现
- 构建可复现：Cargo.lock 锁定依赖版本，镜像内构建无外部网络依赖 (构建工具链镜像见 sandbox runtime)
- 产物可识别：bundle 目录按 target 组织，部署器按目录上传不分发
"""


# ---------------------------------------------------------------------------
# 原型构建指导注册表 — 按 project_type 注入对应脚手架/构建指导
# 新增项目类型时在此注册: key = ProjectType.value, value = 指导文本
# v5.9.0 仅 static_site 实质; binary_app 等在 v6.0.0+ 激活时补充
# ---------------------------------------------------------------------------
PROTOTYPE_BUILD_GUIDES: dict[str, str] = {
    "static_site": PROTOTYPE_ENGINEERING_PROMPT,
    "binary_app": BINARY_APP_BUILD_GUIDE,
}


def get_prototype_guide(project_type: "ProjectType") -> str:
    """按项目类型返回原型构建指导。未注册类型返回空串(由调用方决定 fallback)。"""
    key = project_type.value if hasattr(project_type, "value") else str(project_type)
    return PROTOTYPE_BUILD_GUIDES.get(key, "")


_REFERENCE_PATTERNS = """\
以下模式供参考，根据项目实际情况选用最合适的：

**DDD（领域驱动设计）** — 适合业务逻辑复杂、有明确领域概念的系统
- 聚合 = 事务一致性边界，聚合间 ID 引用
- 值对象优先（不可变 = 安全）
- 限界上下文间通过 ACL/OHS/事件协作
- 领域事件驱动跨上下文通信

**TDD（测试驱动开发）** — 适合有明确验收标准、需要高可靠性的交付
- 从验收标准派生测试用例
- Red → Green → Refactor
- 每个测试对应一个业务不变量

**Clean Architecture** — 适合需要长期维护、技术栈可能变更的系统
- 依赖方向：外层 → 内层
- domain 不依赖框架和基础设施
- 通过接口反转依赖

**Event Sourcing** — 适合需要完整审计轨迹、时间旅行的业务
- 存储事件而非当前状态
- 重放事件重建状态

**CQRS** — 适合读写模式差异大的场景
- 命令（写）和查询（读）分离
- 读模型可针对查询优化

**微服务/模块化单体** — 架构粒度选择
- 微服务：团队独立部署、技术栈异构
- 模块化单体：单进程但模块边界清晰，必要时可拆"""
