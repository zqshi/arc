"""项目宪章 (project_charter) — 项目初始化时按 ProjectType 产出的治理规范 (v6.3.0 T1)。

等价 Arc 自身的 CLAUDE.md, 但交付给每个项目, 且按项目类型裁剪 (T2 特化)。
与 conventions (用户手填的项目特定补充) 并存分工: charter 是系统生成的治理底座,
conventions 是用户增量; 两者都注入 AI 上下文。

意图驱动纪律 (复用 prompt-upgrade #8-10 范式):
- 只给"目标 + 输出契约 + 上下文", 不给机械步骤
- 禁用 Arc 现有规则执行式硬规则 ("文件<500行"/"必须auth"/"必修项"等)
- 让 agent 自主判断如何达成治理目标, 而非套固定阈值

依赖方向单向: charter.py → value_objects(ProjectType); entity.py → charter.py。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.project.value_objects import ProjectType


@dataclass(frozen=True)
class ProjectCharter:
    """项目宪章值对象 — 不可变, 变更通过新建实例。

    持久化为 JSONB (to_dict/from_dict), 与 domain_model/context_policy 同为
    Project 内嵌字段层 (非独立 Artifact 记录, 因 charter 是项目级元数据,
    不绑定 phase/todo)。
    """

    markdown: str
    project_type: ProjectType
    template_version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_empty(self) -> bool:
        return not self.markdown.strip()

    def to_dict(self) -> dict:
        return {
            "markdown": self.markdown,
            "project_type": self.project_type.value,
            "template_version": self.template_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def from_dict(data: dict | None) -> ProjectCharter | None:
        """从持久化 dict 重建。容错: None/缺字段/异常 → None。"""
        if not data or not isinstance(data, dict):
            return None
        try:
            md = data.get("markdown") or ""
            pt_raw = data.get("project_type")
            project_type = ProjectType(pt_raw) if pt_raw else ProjectType.STATIC_SITE
            tv = int(data.get("template_version") or 1)
            ts_raw = data.get("created_at")
            created_at = (
                datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else None
            )
            return ProjectCharter(
                markdown=md,
                project_type=project_type,
                template_version=tv,
                created_at=created_at,
            )
        except (ValueError, TypeError):
            return None


class ConventionTemplateProvider(abc.ABC):
    """规范模板提供者抽象 — 按 ProjectType 返回意图驱动治理规范模板。

    domain 定义契约, application 实现 (T1 默认通用骨架; T2 用 CONVENTION_TEMPLATES
    注册表做类型特化, 与 v5.9.0 get_distributor/get_prototype_guide 同构)。
    新增 ProjectType 时在实现注册表填映射, 不在此加 if 分支。
    """

    @abc.abstractmethod
    def get_template(self, project_type: ProjectType) -> str:
        """返回该类型的意图驱动治理规范模板 markdown。未注册类型由实现决定 fallback。"""
        raise NotImplementedError


# 通用意图驱动治理骨架 — T1 默认实现, 不按类型特化 (T2 替换做特化)。
# T3 深化: 把 Arc 的 4 样治理机制 (版本协议/上下文加载/任务依赖表/质量门禁) 意图驱动化
# 织入对应段落, 让交付项目 agent 能自运转版本切换/质量检测 (传文本即传机制)。
# 禁用规则执行式硬规则 (文件<500行/必须auth/必修项清单等), 只给意图层。
_DEFAULT_CHARTER_TEMPLATE = """\
# 项目治理宪章

本宪章定义本项目迭代治理的意图。开发每次行动前应理解这些意图并自主判断如何达成——
对齐目标, 而非机械执行步骤。

## 上下文加载意图
- 目标: 每次开发行动前, 建立对"当前在做什么、为什么、受什么约束"的理解。
- 输出契约: 开始任何代码变更前, 能复述当前版本的目标、本次任务在版本依赖图中的位置、
  以及任何阻塞前置; 状态不明确时先澄清而非猜测推进。
- 上下文: 项目的版本规划与任务依赖表是理解当前状态的依据。当前版本的目标、范围、约束
  定义在版本规划文档中; 任务的依赖关系与完成状态在依赖表中维护。若这些依据缺失或过时,
  先重建理解再行动, 不在模糊状态下推进。

## 版本迭代意图
- 目标: 交付即不腐烂——每个版本完成时, 代码、文档、测试处于可继续迭代的状态。
- 输出契约: 版本完成态可被验证 (功能可用、测试通过、文档与代码一致)。
- 上下文: 版本切换时, 当前版本归档为只读决策存档 (保留目标/交付/决策/遗留, 删除执行细节),
  下一版本激活承接; 未完成的工作显式结转到新版本, 不静默丢失。归档前确认完成态达标,
  不达则补齐而非放行——只读存档一旦写下不再回改。

## 代码规范意图
- 目标: 代码可维护、职责内聚、依赖方向单向。
- 输出契约: 变更后, 受影响模块的职责仍然单一, 依赖关系不出现环。
- 上下文: 自主判断"这个文件职责是否过重""这次变更是否引入反向依赖""是否需要拆分",
  而非套用固定行数阈值。领域规则内聚在领域对象, 编排逻辑在应用层,
  基础设施与接口层不承载业务判断。

## 质量守护意图
- 目标: 领域模型不腐烂、架构约束不被渐进侵蚀。
- 输出契约: 变更不破坏既有的分层依赖方向, 不引入循环依赖; 版本完成态可被验证——
  无死代码与孤立文件、依赖卫生达标 (引入的包均有使用)、配置一致、文档与实际对齐、
  架构合规、仓库卫生。完成态达标才归档, 不达标补齐。
- 上下文: 发现腐烂信号 (职责泄漏、接口与实现漂移、贫血模型) 时, 主动标记为技术债务
  并标注优先级, 不放任积累。质量检测是完成态的验证手段, 而非流程负担——
  达标的目的是确认可继续迭代, 不是填表。

## 规范维护意图
- 目标: 本宪章随项目演进, 由 agent 与用户共同维护。
- 输出契约: 项目类型变化或治理范式升级时, 宪章相应更新。
- 上下文: 用户补充的项目特定约定 (conventions) 与本宪章并存——
  宪章是系统生成的治理底座, conventions 是项目特定增量。
"""


class DefaultConventionTemplateProvider(ConventionTemplateProvider):
    """T1 默认实现 — 返回通用意图驱动骨架 (不按类型特化)。

    T2 将以 ConventionTemplateRegistry 替换, 按 ProjectType 从
    CONVENTION_TEMPLATES 注册表返回特化模板 (官网=SEO/PWA/性能, 客户端=签名/分发/跨平台)。
    """

    def get_template(self, project_type: ProjectType) -> str:
        return _DEFAULT_CHARTER_TEMPLATE
