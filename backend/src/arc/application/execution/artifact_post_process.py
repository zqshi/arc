"""Artifact 提取后的副作用钩子 (v6.11 T4 从 artifact_extractor.py 拆出)。

ArtifactPostProcessHooks 封装 process_message 在产出 artifact 后触发的副作用:
- _try_extract_domain_model: tech_architecture → 抽领域模型 + 触发 review/baas
- _try_provision_baas_after_extract: 领域模型 → provision BaaS schema
- _try_review_after_extract: 领域模型 → 自动评审
- _try_sync_experience: experience_card → 同步 Experience 实体 (最大单体, 110行)
- infer_deliverable_scope: requirement_spec → 推断裁剪交付物范围

这些钩子全部 graceful (失败仅 warning 不阻断提取主流程), 且不被单元测试直接打桩,
故采用组合类迁出零测试改动 (与 conversation_strategy 的 ConversationContextProvider 同模式)。
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


class ArtifactPostProcessHooks:
    """artifact 提取后的副作用编排, 由 ArtifactExtractor 组合为 self._hooks。

    依赖 db + tracker_repo (infer_deliverable_scope 用)。所有方法 graceful:
    失败仅记录不抛, 避免阻断提取主流程。
    """

    def __init__(self, db, tracker_repo):
        self.db = db
        self._tracker_repo = tracker_repo

    async def try_extract_domain_model(
        self, todo_id: uuid.UUID, content: dict
    ) -> None:
        from arc.application.execution.domain_model_extractor import (
            DomainModelExtractor,
        )

        try:
            extractor = DomainModelExtractor(self.db)
            updated = await extractor.extract_and_merge(todo_id, content)

            # 提取成功后自动触发评审闭环
            if updated:
                await self.try_review_after_extract(todo_id)
                # v5.6.0: 提取成功后自动 provision BaaS (领域模型可执行化)
                await self.try_provision_baas_after_extract(todo_id)
        except Exception:
            logger.warning(
                "Domain model extraction failed for todo %s", todo_id, exc_info=True
            )

    async def try_provision_baas_after_extract(self, todo_id: uuid.UUID) -> None:
        """v5.6.0: 领域模型提取后自动 provision BaaS schema + apply 模型。

        v6.24 治理: 复用 DomainModelService.provision_baas 统一入口, 消除 conversation
        与 pipeline 两处 apply_snapshot 编排重复 (snapshot 构造 + applier 调用下沉到
        service)。失败仅 warning 不阻断 (与 review hook 一致)。
        v6.19 续9: 全路径接入 metrics (result=success|skip|fail + reason) + duration。
        """
        import time

        from arc.application.baas.metrics import (
            BAAS_PROVISION_DURATION,
            BAAS_PROVISION_TOTAL,
        )

        start = time.monotonic()

        def _record(result: str, reason: str) -> None:
            BAAS_PROVISION_TOTAL.labels(result=result, reason=reason).inc()
            BAAS_PROVISION_DURATION.observe(time.monotonic() - start)

        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo_repo = TodoRepository(self.db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo or not todo.project_id:
                _record("skip", "skip_no_project")
                return

            from arc.application.project.domain_model_service import (
                DomainModelService,
            )

            svc = DomainModelService(self.db)
            try:
                result = await svc.provision_baas(todo.project_id)
            except Exception as e:
                # 区分 provision 失败 vs apply_model 失败 (DDL 执行阶段)
                from arc.domain.baas.errors import ProvisionError, SchemaApplyError
                if isinstance(e, SchemaApplyError):
                    _record("fail", "fail_apply")
                elif isinstance(e, ProvisionError):
                    _record("fail", "fail_provision")
                else:
                    _record("fail", "fail_other")
                logger.warning(
                    "BaaS provision after extract failed for todo %s", todo_id,
                    exc_info=True,
                    extra={"todo_id": str(todo_id), "project_id": str(todo.project_id)},
                )
                return  # 不阻断 conversation (原 raise 经外层 except 吞, 等效)

            if result.get("provisioned"):
                logger.info(
                    "BaaS provision triggered for project %s (schema %s)",
                    todo.project_id, result.get("schema_name", ""),
                    extra={"project_id": str(todo.project_id)},
                )
                _record("success", "success")
            else:
                # provision_baas 返回英文 reason_code (no_domain_model/no_aggregates)
                reason_code = result.get("reason_code", "skip_other")
                _record("skip", f"skip_{reason_code}")
                logger.info(
                    "BaaS provision skipped: todo %s reason=%s",
                    todo_id, reason_code,
                    extra={"todo_id": str(todo_id), "project_id": str(todo.project_id)},
                )
        except Exception:
            logger.warning(
                "BaaS provision after extract failed for todo %s", todo_id, exc_info=True,
                extra={"todo_id": str(todo_id)},
            )
            _record("fail", "fail_other")

    async def try_sync_experience(
        self, todo_id: uuid.UUID, content: dict
    ) -> None:
        """experience_card 产出后，自动创建 Experience 实体同步到 experiences 表。"""
        from arc.domain.experience.entity import Experience
        from arc.domain.todo.value_objects import (
            ExperienceCategory,
            ExperienceScope,
            ExperienceSource,
            ExperienceStatus,
            Tag,
        )
        from arc.infrastructure.repositories.experience import ExperienceRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo_repo = TodoRepository(self.db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo:
                return

            # 去重：如果已经从这个 todo 同步过经验，跳过
            exp_repo = ExperienceRepository(self.db)
            from sqlalchemy import select

            from arc.infrastructure.models.experience import Experience as ExpModel
            existing = await self.db.execute(
                select(ExpModel.id).where(ExpModel.todo_id == todo_id).limit(1)
            )
            if existing.scalar_one_or_none():
                logger.debug(
                    "Experience already exists for todo %s, skip sync", todo_id
                )
                return

            problem = content.get("problem", "")
            solution = content.get("solution", "")
            if not problem or not solution:
                logger.info(
                    "experience_card for todo %s missing problem/solution, skip sync",
                    todo_id,
                )
                return

            # 解析 decisions
            raw_decisions = content.get("decisions", [])
            decisions: list[str | dict] = []
            if isinstance(raw_decisions, list):
                for d in raw_decisions:
                    if isinstance(d, dict):
                        decisions.append(d)
                    elif isinstance(d, str):
                        decisions.append(d)

            # 解析 pitfalls
            raw_pitfalls = content.get("pitfalls", [])
            pitfalls: list[str | dict] = []
            if isinstance(raw_pitfalls, list):
                for p in raw_pitfalls:
                    if isinstance(p, dict):
                        pitfalls.append(p)
                    elif isinstance(p, str):
                        pitfalls.append(p)

            # 解析 tags
            raw_tags = content.get("tags", [])
            tags = [Tag(label=t, color="#888888") for t in raw_tags if isinstance(t, str)]

            # 解析 category
            raw_category = content.get("category", "technical")
            try:
                category = ExperienceCategory(raw_category)
            except ValueError:
                category = ExperienceCategory.TECHNICAL

            experience = Experience(
                todo_id=todo.id,
                project_id=todo.project_id,
                version_id=todo.version_id,
                scope=ExperienceScope.PROJECT,
                status=ExperienceStatus.DRAFT,
                category=category,
                source=ExperienceSource.TODO_COMPLETION,
                title=content.get("title", todo.title),
                problem=problem,
                solution=solution,
                decisions=decisions,
                pitfalls=pitfalls,
                applicable_scenarios=content.get("applicable_scenarios", ""),
                tags=tags,
                confidence=0.7,
                metadata={
                    "synced_from": "experience_card_artifact",
                    "reuse_checklist": content.get("reuse_checklist", []),
                },
            )

            exp_repo = ExperienceRepository(self.db)
            created = await exp_repo.create(experience)
            logger.info(
                "Synced experience_card to Experience %s for todo %s",
                created.id,
                todo_id,
            )
        except Exception:
            logger.warning(
                "Experience sync from artifact failed for todo %s",
                todo_id,
                exc_info=True,
            )

    async def try_review_after_extract(self, todo_id: uuid.UUID) -> None:
        """领域模型提取后自动触发评审，产出 ReviewFeedback。"""
        from arc.application.review.service import ReviewService
        from arc.infrastructure.repositories.review import ReviewFeedbackRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo_repo = TodoRepository(self.db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo or not todo.project_id:
                return

            from arc.infrastructure.repositories.project import ProjectRepository

            project_repo = ProjectRepository(self.db)
            project = await project_repo.get_by_id(todo.project_id)
            if not project or not project.domain_model:
                return

            feedback_repo = ReviewFeedbackRepository(self.db)
            svc = ReviewService(feedback_repo)
            await svc.validate_and_persist(
                project.id, project.domain_model, source_todo_id=todo_id,
            )
        except Exception:
            logger.debug("Auto-review after extract skipped for todo %s", todo_id, exc_info=True)

    async def infer_deliverable_scope(
        self, tracker, req_spec: dict,
    ) -> None:
        """根据 requirement_spec 内容推断适用的交付物范围，裁剪 tracker.required。

        规则基于需求类型特征词匹配，不调用 LLM（零延迟）：
        - 无 UI 相关描述 → 跳过 interaction_design, ui_spec, prototype
        - 纯 bug 修复 → 只保留核心四项
        - 其他保留全量
        """
        from arc.domain.planning.value_objects import DeliverableStatus
        from arc.domain.project.value_objects import REQUIRED_DELIVERABLES

        # 提取信号
        stories = req_spec.get("user_stories", [])
        boundaries = req_spec.get("boundaries", {})
        in_scope = boundaries.get("in_scope", []) if isinstance(boundaries, dict) else []
        background = req_spec.get("background", "")
        all_text = (
            background + " "
            + " ".join(str(s) for s in stories)
            + " ".join(str(s) for s in in_scope)
        ).lower()

        # 判断需求类型
        has_ui_signal = any(kw in all_text for kw in [
            "ui", "界面", "页面", "交互", "前端", "组件", "按钮", "表单",
            "弹窗", "列表", "视觉", "样式", "布局", "响应式", "移动端",
        ])
        is_bug_fix = any(kw in all_text for kw in [
            "bug", "修复", "fix", "回归", "崩溃", "报错", "异常",
        ]) and not any(kw in all_text for kw in ["新增", "新功能", "feature"])

        has_deploy_signal = any(kw in all_text for kw in [
            "部署", "上线", "deploy", "ci", "cd", "docker", "k8s",
        ])

        # 计算适用范围
        skip_types: set[str] = set()

        if not has_ui_signal:
            skip_types.update(["interaction_design", "ui_spec", "prototype"])

        if is_bug_fix:
            skip_types.update([
                "interaction_design", "ui_spec", "prototype",
                "tech_architecture", "deploy_report",
            ])

        if not has_deploy_signal and not is_bug_fix:
            # 默认保留 deploy_report，但纯前端任务可跳过
            has_backend_signal = any(kw in all_text for kw in [
                "api", "后端", "数据库", "服务", "接口", "backend",
            ])
            if not has_backend_signal and has_ui_signal:
                skip_types.add("deploy_report")

        # 应用裁剪
        if not skip_types:
            return  # 全量保留，不修改

        new_required = [d for d in REQUIRED_DELIVERABLES if d not in skip_types]

        # 不能裁剪到少于 4 项（最低保障）
        if len(new_required) < 4:
            return

        # 更新 tracker
        tracker.required = new_required
        # 移除被跳过项的 pending 状态（已产出的保留）
        for skip_type in skip_types:
            if tracker.deliverables.get(skip_type) == DeliverableStatus.PENDING:
                del tracker.deliverables[skip_type]

        await self._tracker_repo.update(tracker)
        logger.info(
            "Inferred deliverable scope: skipped %s, remaining %d items",
            skip_types, len(new_required),
        )
