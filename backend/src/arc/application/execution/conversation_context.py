"""对话上下文查询与 greeting 生成 (v6.11 T4 从 conversation_strategy.py 拆出)。

ConversationContextProvider 封装所有"从 db 读取项目/版本上下文"的查询:
- greeting 组: 上下文感知开场白 (基于版本分析缓存 + todo 来源 + 描述丰富度, 不调 LLM)
- 项目配置查询: local_path / sandbox_policy / orchestration / llm_config

这些查询原为 ConversationExecutionService 的私有方法, 被测试以
`patch.object(service, "_get_...")` 打桩, 故采用组合类而非模块级函数,
保持打桩点从 service 平移到 service._context (见 test_conversation_strategy.py)。
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


class ConversationContextProvider:
    """从 db 读取项目/版本上下文 + 生成上下文感知 greeting。

    由 ConversationExecutionService 组合为 self._context, 所有查询方法
    只依赖 db 与 todo_repo, 不持有可变状态。
    """

    def __init__(self, db, todo_repo):
        self.db = db
        self._todo_repo = todo_repo

    # ------------------------------------------------------------------
    # Greeting (上下文感知开场白, 不调 LLM)
    # ------------------------------------------------------------------

    async def build_context_aware_greeting(self, todo) -> str:
        """基于版本分析缓存 + todo 来源 + 描述丰富度生成上下文感知的开场白。

        不调用 LLM，纯粹基于已有数据动态组装。
        """
        constraint = await self.get_project_constraint(todo)
        parts: list[str] = []

        # 1. 开头 — 表明意图
        parts.append(f"你好！我来帮你完成「{todo.title}」。")

        # 2. 版本分析洞察（如果有缓存 — 展示 AI 对项目状态的理解）
        analysis_insight = await self.get_analysis_insight_for_greeting(todo)
        if analysis_insight:
            parts.append(analysis_insight)

        # 3. 来源感知 — AI建议来源的需求展示理解
        if todo.source_session_id:
            parts.append(
                "这个需求来自版本分析建议，我已了解其背景和优先级定位。"
            )

        # 4. 流程说明 — 基于 constraint 级别
        if constraint == "strict":
            parts.append(
                "我会按标准研发流程逐步推进，每阶段产出结构化交付物，"
                "通过门禁确认后进入下一阶段。右侧面板实时展示进度。"
            )
        elif constraint == "moderate":
            parts.append(
                "我会在对话中自动产出结构化交付物，"
                "你可以随时在右侧面板查看进度和已产出成果。"
            )
        # free 模式不做流程声明 — 自然对话

        # 5. 需求理解 + 引导
        if todo.description:
            desc_preview = todo.description[:300]
            has_rich_context = (
                len(todo.description) > 50
                or todo.description.startswith("[P")
                or bool(todo.source_session_id)
            )
            parts.append(f"需求描述：{desc_preview}")
            if has_rich_context:
                parts.append(
                    "背景信息已足够清晰，我直接开始推进。"
                    "如有需要补充的随时告诉我。"
                )
            else:
                parts.append("先聊聊这个需求要解决什么问题？有哪些关键的用户场景？")
        else:
            parts.append("先描述一下你想做什么？解决什么问题？")

        return "\n\n".join(parts)

    async def get_analysis_insight_for_greeting(self, todo) -> str:
        """从版本分析缓存中提取一句精简洞察用于 greeting。"""
        if not todo.version_id:
            return ""
        try:
            from arc.application.planning.analysis_service import AnalysisService

            svc = AnalysisService(self.db)
            result = await svc.get_latest(todo.version_id)
            if not result:
                return ""

            _, suggestions = result
            if not suggestions:
                return ""

            # 提取与当前 todo 相关的建议（如有）或总体概况
            related = [
                s for s in suggestions
                if todo.title.lower() in s.get("action", "").lower()
            ]
            if related:
                s = related[0]
                return (
                    f"版本分析中对此需求的定位：**[{s.get('priority', '?')}]** "
                    f"{s.get('reason', s.get('action', ''))}"
                )

            # 无直接相关的，给出版本整体状况
            p0_count = sum(1 for s in suggestions if s.get("priority") == "P0")
            if p0_count:
                return f"当前版本有 {p0_count} 项 P0 优先事项，我会注意与它们的协调。"
            return ""
        except Exception:
            return ""

    async def get_project_constraint(self, todo) -> str:
        """获取项目的 process_constraint 级别。"""
        if not todo or not todo.project_id:
            return "free"
        from arc.infrastructure.repositories.project import ProjectRepository
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return "free"
        return project.process_constraint.value

    # ------------------------------------------------------------------
    # 项目配置查询
    # ------------------------------------------------------------------

    async def get_project_local_path(self, todo_id: uuid.UUID) -> str | None:
        from pathlib import Path

        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self._todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.local_path:
            return None
        resolved = Path(project.local_path).expanduser().resolve()
        if resolved.is_dir():
            return str(resolved)
        logger.warning("Project local_path does not exist: %s", project.local_path)
        return None

    async def get_sandbox_policy(self, todo_id: uuid.UUID):
        """构造 sandbox 策略 — 策略解析逻辑见 sandbox.policy_resolver。

        BINARY_APP 默认启用容器化构建 + 镜像推导 (断点A/B) 由
        resolve_sandbox_policy 处理; 本方法只做 db 查询接线。
        """
        from arc.application.sandbox.policy_resolver import resolve_sandbox_policy
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self._todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return None
        return resolve_sandbox_policy(project)

    async def is_orchestration_enabled(self, todo_id: uuid.UUID) -> bool:
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self._todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return False
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return False
        orch_cfg = project.conversation_config.get("orchestration", {})
        return bool(orch_cfg.get("enabled", False))

    async def get_llm_config(self, todo_id: uuid.UUID) -> dict | None:
        """获取项目级 LLM 配置 (v6.21 D1+D3 统一走 LLMProviderService)。

        优先级链 (项目 llm_provider_id → 旧明文 → 用户默认 → None) 见
        LLMProviderService.resolve_from_project; 此处只做 todo→project 查询接线。
        解密 + DB 凭证查询收敛进 LLMProviderService, 不再直接依赖
        infrastructure/crypto 与 SqlAlchemyLLMProviderRepository (减轻 execution 层
        对 infrastructure 的直接依赖)。
        """
        from arc.application.llm.service import LLMProviderService
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self._todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return None
        return await LLMProviderService(self.db).resolve_from_project(
            project, project.user_id
        )
