from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.application.pipeline.prompt_registry import prompt_registry
from arc.application.pipeline.prompts import PHASE_EXTRACTION_PROMPTS
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.policy import filter_editable_fields
from arc.domain.artifact.value_objects import PHASE_PRIMARY_ARTIFACT, ArtifactType
from arc.domain.errors import AppError
from arc.domain.pipeline.value_objects import PhaseType
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository

logger = logging.getLogger(__name__)


class ArtifactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.artifact_repo = ArtifactRepository(db)
        self.phase_repo = PipelinePhaseRepository(db)
        self.conv_repo = ConversationRepository(db)

    @staticmethod
    def _get_extraction_prompt(phase_type):
        """Get extraction prompt for the given phase type."""
        return PHASE_EXTRACTION_PROMPTS.get(phase_type)

    async def generate_from_conversation(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> Artifact | None:
        """Use LLM to extract structured artifact from a phase's conversation."""
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase or not phase.conversation_id:
            logger.error("generate_artifact: no conversation for phase %s", phase_type)
            return None

        conv = await self.conv_repo.get_by_id(phase.conversation_id)
        if not conv:
            return None

        extraction_prompt = self._get_extraction_prompt(phase_type)
        if not extraction_prompt:
            return None

        messages = []
        messages.append(
            LLMMessage(
                role="system",
                content="根据对话内容生成结构化输出。",
            )
        )
        for msg in conv.messages:
            if msg.role.value != "system":
                messages.append(LLMMessage(role=msg.role.value, content=msg.content))
        messages.append(LLMMessage(role="user", content=extraction_prompt))

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat(messages, temperature=0.3)
        finally:
            await adapter.close()

        content = extract_json(response.content)
        if content is None or not isinstance(content, dict):
            logger.error("generate_artifact: failed to parse response for %s", phase_type)
            return None

        content["_meta"] = {
            "prompt_version": prompt_registry.get_version(phase_type, "extraction"),
            "model": response.model,
            "usage": response.usage,
        }

        artifact_type = PHASE_PRIMARY_ARTIFACT[phase_type]
        existing = await self.artifact_repo.get_by_phase_id(phase.id)

        if existing:
            existing.update_content(content)
            return await self.artifact_repo.update(existing)
        else:
            artifact = Artifact(
                todo_id=todo_id,
                phase_id=phase.id,
                artifact_type=artifact_type,
                content=content,
            )
            return await self.artifact_repo.create(artifact)

    async def update_content(
        self,
        artifact_id: uuid.UUID,
        new_content: dict,
        *,
        partial: bool = False,
    ) -> Artifact | None:
        """User edits artifact content.

        v5.5.0 起增加字段可编辑性校验 (domain/artifact/policy.py):
        - 文档类 artifact: 任意字段可改 (向后兼容旧行为)
        - 工程产物 (APP_CODE/PROTOTYPE): 全只读，调用方应直接拒绝
        - 结构化 artifact (SERVICE_SPEC): 仅 notes 等白名单字段可改

        Args:
            new_content: 用户提交的内容
            partial: True 时合并到原 content (只覆盖提供字段)；False 时整体替换
        """
        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact:
            return None

        _, rejected = filter_editable_fields(artifact.artifact_type, new_content.keys())
        if rejected:
            raise AppError(
                f"不可编辑字段: {', '.join(sorted(rejected))} "
                f"(artifact_type={artifact.artifact_type.value})"
            )

        merged = {**artifact.content, **new_content} if partial else new_content
        artifact.update_content(merged)
        return await self.artifact_repo.update(artifact)

    async def confirm(
        self, artifact_id: uuid.UUID, *, llm_review_fn=None
    ) -> Artifact | None:
        """Mark artifact as confirmed.

        requirement_spec 确认前过 sufficiency 门禁 (产出前判断对话信息是否足够,
        v6.0 #7)。信息不足抛 ValueError (带 follow_up_questions), 由 route 转 400。
        llm_review_fn 可注入用于测试。
        """
        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact:
            return None
        if artifact.artifact_type == ArtifactType.REQUIREMENT_SPEC:
            await self._check_sufficiency(artifact, llm_review_fn=llm_review_fn)
        artifact.confirm()
        return await self.artifact_repo.update(artifact)

    async def _check_sufficiency(
        self, artifact: Artifact, *, llm_review_fn=None
    ) -> None:
        """requirement_spec 产出前 sufficiency 门禁 — 判断对话信息是否足够。

        从 todo 取 title/description, 从对话历史拼 summary, 调 evaluate_sufficiency
        三维评估。sufficient=false 抛 ValueError 阻断确认。门禁异常降级放行 (不阻断)。
        """
        from arc.application.execution.sufficiency_gate import evaluate_sufficiency
        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo = await TodoRepository(self.db).get_by_id(artifact.todo_id)
            title = getattr(todo, "title", "") if todo else ""
            description = getattr(todo, "description", "") if todo else ""

            convs = await self.conv_repo.list_by_todo_id(artifact.todo_id)
            summary_parts: list[str] = []
            for conv in convs:
                for msg in conv.messages:
                    role = getattr(msg.role, "value", str(msg.role))
                    summary_parts.append(f"{role}: {msg.content}")
            # 截断防爆 (取最近 2000 字符, 信息密度集中在近期对话)
            conversation_summary = "\n".join(summary_parts)[-2000:]

            result = await evaluate_sufficiency(
                title=title,
                description=description,
                conversation_summary=conversation_summary,
                llm_review_fn=llm_review_fn,
            )
            if not result.sufficient:
                questions = result.follow_up_questions or [
                    "请补充目标用户、核心问题、功能方向"
                ]
                raise AppError(
                    f"需求信息尚不充分, 暂无法确认需求规格: {'; '.join(questions)}"
                )
        except (ValueError, AppError):
            raise  # 阻断信号向上透传
        except Exception as exc:
            logger.warning(
                "sufficiency gate skipped for artifact %s: %s", artifact.id, exc
            )
            # 门禁异常降级放行, 不阻断确认 (遵循降级原则)

    async def get_confirmed_context(self, todo_id: uuid.UUID) -> dict[ArtifactType, dict]:
        """Get all confirmed artifacts for a todo, keyed by type."""
        artifacts = await self.artifact_repo.list_confirmed_by_todo(todo_id)
        return {a.artifact_type: a.content for a in artifacts}

    async def get_by_phase(self, todo_id: uuid.UUID, phase_type: PhaseType) -> Artifact | None:
        """Get the artifact for a specific phase."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            return None
        return await self.artifact_repo.get_by_phase_id(phase.id)

    # v6.9 — BUILD artifact (构建产物锚点): builder 产出 / 签名 / 分发统一锚点

    async def create_or_update_build(
        self,
        todo_id: uuid.UUID,
        phase_id: uuid.UUID | None,
        *,
        build_target: str,
        artifact_path: str,
        build_status: str,
        build_log: str | None = None,
        signature_status: str | None = None,
        distribution_status: str | None = None,
        product_path: str | None = None,
    ) -> Artifact:
        """v6.9: builder 产出构建产物后写入 BUILD artifact(锚点)。

        DEVELOPMENT 阶段构建完成 → 创建/更新 BUILD artifact, 记录 build_target/
        产物路径/构建状态。签名/分发状态预留 None, ④接入时 update_build_status
        回写。构建产物 per todo 唯一(一个 BUILD artifact), 已存在则增量更新。
        """
        content: dict = {
            "build_target": build_target,
            "artifact_path": artifact_path,
            "build_status": build_status,
        }
        if build_log is not None:
            content["build_log"] = build_log
        if signature_status is not None:
            content["signature_status"] = signature_status
        if distribution_status is not None:
            content["distribution_status"] = distribution_status
        if product_path is not None:
            content["product_path"] = product_path

        existing = await self._find_build_artifact(todo_id)
        if existing:
            existing.update_content(content)
            return await self.artifact_repo.update(existing)
        artifact = Artifact(
            todo_id=todo_id,
            phase_id=phase_id,
            artifact_type=ArtifactType.BUILD,
            content=content,
        )
        return await self.artifact_repo.create(artifact)

    async def update_build_status(
        self,
        artifact_id: uuid.UUID,
        *,
        build_status: str | None = None,
        signature_status: str | None = None,
        distribution_status: str | None = None,
        product_path: str | None = None,
    ) -> Artifact | None:
        """v6.9: 回写构建产物状态(构建/签名/分发), ④接入点调用。

        增量合并到 BUILD content(不覆盖未提供字段)。直接走 entity.update_content
        (绕过 filter_editable_fields — BUILD 是工程产物 UI 只读, 但此处是 service
        内部回写, 非 UI 编辑)。
        """
        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact:
            return None
        if artifact.artifact_type != ArtifactType.BUILD:
            raise AppError(
                "update_build_status 仅适用 BUILD artifact, 实际 "
                f"{artifact.artifact_type.value}"
            )
        updates: dict[str, str] = {}
        if build_status is not None:
            updates["build_status"] = build_status
        if signature_status is not None:
            updates["signature_status"] = signature_status
        if distribution_status is not None:
            updates["distribution_status"] = distribution_status
        if product_path is not None:
            updates["product_path"] = product_path
        if updates:
            merged = {**artifact.content, **updates}
            artifact.update_content(merged)
            return await self.artifact_repo.update(artifact)
        return artifact

    async def _find_build_artifact(self, todo_id: uuid.UUID) -> Artifact | None:
        """查找 todo 的 BUILD artifact(构建产物 per todo 唯一)。"""
        arts = await self.artifact_repo.list_by_todo_id(todo_id)
        return next(
            (a for a in arts if a.artifact_type == ArtifactType.BUILD), None
        )
