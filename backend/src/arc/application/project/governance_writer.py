"""治理产物落盘服务 — 把 charter 与治理上下文写成交付项目 local_path 下的文件 (v6.3.0 T3)。

两层传递的第二层 (机制层): 只传 charter 文本不传机制则文本交付即腐烂。
落盘交付文件让交付项目的 agent 有可自运转版本切换/质量检测的工件入口。

交付文件 (落盘位置 = 项目根, 用户已确认 github 类型接受写仓库根):
- {local_path}/CLAUDE.md            — agent 入口, charter 的操作投影 (4 样机制操作意图)
- {local_path}/.arc/governance/CHARTER.md — charter 文本原文 (治理底座)

设计:
- 幂等: write_text 覆盖语义, 重复调用 (charter 升级/local_path 就绪后补落盘) 不追加。
- 无 DB 副作用: 只写文件, charter 已在 Project.charter (DB JSONB)。
- graceful skip: local_path 空 (github clone 前) 或 charter 空 → 静默跳过不抛。
- 意图驱动: CLAUDE.md 是 charter 操作投影, 禁 Arc 规则执行式硬规则。
"""
from __future__ import annotations

from pathlib import Path

from arc.domain.project.entity import Project


class GovernanceArtifactWriter:
    """把 charter 与治理上下文写成交付项目 local_path 下的文件。"""

    CHARTER_REL = ".arc/governance/CHARTER.md"
    CONTEXT_REL = "CLAUDE.md"

    def write(self, project: Project) -> None:
        """落盘 CHARTER.md + CLAUDE.md。local_path 未就绪或 charter 空 → 静默跳过。"""
        if not project.local_path:
            return  # github 类型 clone 前 local_path 为空, 待 clone 后补落盘
        if not project.charter or project.charter.is_empty():
            return  # charter 未初始化, 跳过

        base = Path(project.local_path).expanduser().resolve()
        charter_path = base / self.CHARTER_REL
        charter_path.parent.mkdir(parents=True, exist_ok=True)
        charter_path.write_text(project.charter.markdown, encoding="utf-8")

        context_path = base / self.CONTEXT_REL
        context_path.write_text(self._render_context_md(project), encoding="utf-8")

    def _render_context_md(self, project: Project) -> str:
        """生成 CLAUDE.md — charter 的操作投影, 4 样机制操作意图 + conventions + 索引。"""
        lines: list[str] = [
            f"# {project.name} 治理上下文",
            "",
            "> 本文件由 Arc 生成, 是项目宪章 (`.arc/governance/CHARTER.md`) 的操作投影。",
            "> 宪章定义治理意图, 本文件定义每次开发会话如何落实这些意图。",
            "",
            "## 上下文加载意图",
            "- 目标: 每次开发行动前, 建立对当前版本目标、本次任务位置、阻塞前置的理解。",
            "- 输出契约: 开始代码变更前, 能复述这三点; 状态不明先澄清而非猜测推进。",
            "- 上下文依据: `.arc/governance/CHARTER.md` (治理意图) 与 `.arc/versions/` "
            "(版本规划, 若存在)。依据缺失或过时先重建理解。",
            "",
            "## 版本迭代意图",
            "- 目标: 交付即不腐烂——版本完成时代码、文档、测试处于可继续迭代状态。",
            "- 输出契约: 版本完成态可被验证 (功能可用、测试通过、文档与代码一致)。",
            "- 上下文: 版本切换时当前版本归档为只读决策存档, 下一版本激活承接; "
            "未完成工作显式结转不静默丢失。归档前确认达标, 不达则补齐。",
            "",
            "## 任务编排意图",
            "- 目标: 工作按依赖关系推进, 不在 blocked 状态强行开工。",
            "- 输出契约: 接到需求时, 先定位其在当前版本任务依赖表中的位置与状态, "
            "再决定执行顺序。",
            "- 上下文: 依赖图与任务状态在版本规划文档中维护。计划外工作显式入表, "
            "不静默插队。",
            "",
            "## 质量守护意图",
            "- 目标: 领域模型不腐烂、架构约束不被渐进侵蚀。",
            "- 输出契约: 变更不破坏分层依赖方向, 不引入循环依赖; 完成态可被验证——"
            "无死代码、依赖卫生达标、配置一致、文档对齐、架构合规、仓库卫生。",
            "- 上下文: 发现腐烂信号 (职责泄漏、接口与实现漂移、贫血模型) 时, "
            "主动标记为技术债务并标注优先级, 不放任积累。",
            "",
        ]

        if project.conventions and project.conventions.strip():
            lines.extend([
                "## 项目特定治理",
                "",
                project.conventions.strip(),
                "",
            ])

        lines.extend([
            "## 关键文档索引",
            "",
            "| 文档 | 用途 |",
            "|------|------|",
            "| `.arc/governance/CHARTER.md` | 治理宪章 (意图驱动) |",
            "| `.arc/versions/` | 版本规划 (版本切换时由 agent 维护) |",
            "",
        ])
        return "\n".join(lines)
