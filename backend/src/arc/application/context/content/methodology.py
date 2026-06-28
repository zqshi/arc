"""方法论内容显性化 (B方案/T2) — methodology prompt 文本集中声明。

纯内容 (prompt 文本) 从 constraint_policy.py / context/prompts.py 迁入此模块,
消费方 (get_methodology_prompt_for_constraint / MethodologyProvider._build) 改读本模块。
编排逻辑 (constraint 分发 / clarification_strategy 路由 / *_methodology 子步骤) 保留原模块。

复用 v6.9 dict + .get(key, default) fallback 模式 (DELIVERABLES_BY_TYPE 范式)。
载体: Python 常量模块 (非 YAML, 零新依赖, 见 v6.10 T1 设计)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.domain.project.value_objects import ProjectType


# ---------------------------------------------------------------------------
# free 模式质量底线 (by phase) — 迁自 constraint_policy._quality_baseline_prompt
# 不约束怎么做, 但明确做到什么标准才算完
# ---------------------------------------------------------------------------
FREE_BASELINES: dict[str, str] = {
    "clarification": """\
## 质量底线
产出 requirement_spec 时，以下字段不得为空或占位：
- target_users（至少 1 个具体角色）
- user_stories（至少覆盖核心场景）
- acceptance_criteria（每个 P0 story 至少 1 条 AC）
- boundaries.in_scope + out_of_scope""",

    "ui_design": """\
## 质量底线
产出 interaction_design 时：
- user_flows 每个流程有完整 mermaid 流程图
- page_map 标注页面间跳转关系
- 至少定义空状态和加载态

产出 ui_spec 时：
- design_tokens 必须包含 colors + typography + spacing
- component_specs 每个组件有 states 描述和尺寸规范

产出 prototype 时：
- pages 每页有完整可渲染 HTML（含 Tailwind）
- 标注对应用户场景
- 核心操作路径 ≤ 3 步可达""",

    "architecture": """\
## 质量底线
产出 tech_architecture 时：
- tech_decisions 每个决策必须有 ≥2 个候选方案
- data_model.entities 与 user_stories 对齐
- 不得有上下文间循环依赖""",

    "development": """\
## 质量底线
产出 dev_report 时：
- test_results 不得包含 FAIL/ERROR
- code_changes 不得为空""",

    "testing": """\
## 质量底线
产出 test_report 时：
- criteria_verification 逐条覆盖 P0 验收标准
- 每个 pass 必须有 evidence（不接受无证据的自述）""",

    "deployment": """\
## 质量底线
产出 deploy_report 时：
- deploy_log.steps_executed 每步有明确 status
- health_check_result 至少检查一个关键端点
- rollback_plan 不得为空""",

    "extraction": """\
## 质量底线
产出 experience_card 时：
- problem + solution 不得为占位文本
- decisions 至少包含 1 个有 options_considered 的决策点
- pitfalls 记录至少 1 个实际遇到的问题""",
}


# ---------------------------------------------------------------------------
# moderate 精简 prompt (by phase) — 迁自 constraint_policy._xxx_prompt 的 moderate 分支
# strict 分支 (调 clarification_strategy / *_methodology 等子模块) 是编排逻辑, 保留原模块
# ---------------------------------------------------------------------------
MODERATE_PROMPTS: dict[str, str] = {
    "clarification": """\
## 需求澄清（精简模式）

快速确认以下六项，有答案即可产出：
1. **目标用户** — 谁在用？
2. **使用场景** — 什么情境触发？
3. **核心痛点** — 当前怎么解决的？为什么不够好？
4. **功能方向** — 大致做什么？
5. **边界** — 明确不做什么？
6. **成功标准** — 做到什么程度算完？

信息足够时直接产出交付物，不必追问到完美。""",

    "ui_design": """\
## 交互设计（精简模式）

产出 wireframe 时注意：
- 每页标注对应的用户场景
- 定义空状态和加载态
- 核心操作路径 ≤ 3 步""",

    "architecture": """\
## 技术架构（精简模式）

产出时确保：
- 每个技术决策有 ≥2 个候选方案 + 选择理由
- 数据模型与需求中的用户故事对齐
- API 设计覆盖核心场景""",

    "development": """\
## 开发（精简模式）

建议测试优先，但不强制 TDD 循环。完成前确认测试通过。""",

    "testing": """\
## 测试（精简模式）

逐条对照验收标准，每条 pass/fail 需有证据。""",
}


# ---------------------------------------------------------------------------
# 原型工程化指导 (by project_type) — 迁自 context/prompts.py
# 新增项目类型时在此注册: key = ProjectType.value, value = 指导文本
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
- Capacitor 7 android 构建须统一 kotlin stdlib 版本：capacitor 7 依赖 kotlin-stdlib 1.8.22，
  若 androidx 等传递引入旧 kotlin-stdlib-jdk8 (如 1.6.21) 会触发 checkDuplicateClasses 失败
  (重复类)。在 android/build.gradle 用 configurations.all 的 resolutionStrategy.force
  统一 kotlin-stdlib 与 kotlin-stdlib-jdk8 到同版本 (1.8.22)，且 ext.kotlin_version 与
  capacitor 要求对齐——这是 release 构建能否过 checkDuplicateClasses 的关键

### 设计原则

- 复用前端工程：web 资源与 static_site 共用 src/，避免重复实现
- 构建可复现：Cargo.lock 锁定依赖版本，镜像内构建无外部网络依赖 (构建工具链镜像见 sandbox runtime)
- 产物可识别：bundle 目录按 target 组织，部署器按目录上传不分发
"""

PROTOTYPE_BUILD_GUIDES: dict[str, str] = {
    "static_site": PROTOTYPE_ENGINEERING_PROMPT,
    "binary_app": BINARY_APP_BUILD_GUIDE,
}


def get_prototype_guide(project_type: "ProjectType") -> str:
    """按项目类型返回原型构建指导。未注册类型返回空串(由调用方决定 fallback)。"""
    key = project_type.value if hasattr(project_type, "value") else str(project_type)
    return PROTOTYPE_BUILD_GUIDES.get(key, "")
