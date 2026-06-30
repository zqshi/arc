"""Build tool — CI target 原生客户端构建 Agent 工具 (v6.19 T3-g 设计2)。

仅 CI target (Windows/iOS/鸿蒙) 注册; docker target 用 run_command (零改动, 设计2)。
Agent 调 build → tar 代码 → upload → presigned_url → dispatch_build (立即返回)
→ 后台 asyncio task await_build (独立 db session) + stream_manager 推 build_complete。

仿 register_baas_tools 闭包注入模式 (tools.py:187), 不改 ToolRegistry.__init__。

端到端 blocked: 需 gha_token + windows/macos runner + S3(source_url)。本地 dev 无 S3
(presigned_url raise), 仅 mock 验证 dispatch/await 契约。

已知妥协 (端到端验证后补):
- source tarball max_size=DEPLOY_MAX_UPLOAD_SIZE(50MB, 大项目可能超限需分块)
- phase_id=None (BUILD artifact 无 phase 归属, CI target 无 prototype 锚点)
- 后台 task fire-and-forget (异常 try/except + stream_manager 告知, 无 task registry)
"""
from __future__ import annotations

import asyncio
import io
import logging
import tarfile
from pathlib import Path
from uuid import UUID

from arc.application.execution.tool_definitions import ToolDefinition
from arc.domain.sandbox.execution_backend import (
    BuildExecutionBackend,
    target_execution_backend,
)
from arc.domain.sandbox.value_objects import BuildTarget

logger = logging.getLogger(__name__)

# tar 排除的大目录 (build 产物/依赖, CI 不需, 减小体积)
_TAR_EXCLUDES = {"node_modules", ".git", "target", "dist", "build", ".venv", "__pycache__"}


def make_build_tool(
    *,
    build_target: BuildTarget,
    todo_id: UUID,
    db,
    conversation_id: str,
    local_dir: str,
) -> ToolDefinition | None:
    """构造 build 工具 (CI target 专属); 非 CI target 返回 None (不注册)。

    handler 闭包捕获上下文 (todo_id/db/conversation_id/local_dir/build_target)。
    """
    if target_execution_backend(build_target) != BuildExecutionBackend.CI:
        return None  # docker target 不注册 build 工具 (用 run_command)

    bt = build_target
    tid = todo_id
    db_ = db
    cid = conversation_id
    ld = local_dir

    async def _build(params: dict) -> str:
        source_url = await _upload_source(ld, tid)
        await _dispatch(bt, db_, tid, source_url)
        # 后台 task 轮询/下载/记录 success (独立 session, 不阻塞对话)
        asyncio.create_task(_background_await(bt, tid, ld, cid))
        return (
            f"CI 构建已派发 (target={bt.value}), 预计数分钟完成。"
            "构建在 GitHub Actions 异步执行, 完成后产物自动接入, 可签名分发。"
        )

    return ToolDefinition(
        name="build",
        description=(
            "触发原生客户端构建 (CI target: Windows/iOS/鸿蒙)。CI 异步构建, 立即派发不阻塞对话。"
            "完成后产物自动接入 BUILD artifact, 可签名分发。"
            "BINARY_APP 原生构建唯一入口 — 勿用 run_command 跑构建命令 (CI target 宿主无法构建)。"
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_build,
    )


async def _upload_source(local_dir: str, todo_id: UUID) -> str:
    """tar 项目代码 (排除大目录) → upload → presigned_url (CI 下载构建用)。"""
    from arc.infrastructure.storage import DEPLOY_MAX_UPLOAD_SIZE, get_storage

    tarball = _make_tarball(local_dir)
    storage = get_storage()
    key = f"builds/{todo_id}/source.tar.gz"
    await storage.async_upload(
        key, tarball, "application/gzip", max_size=DEPLOY_MAX_UPLOAD_SIZE
    )
    return await storage.async_presigned_url(key)


def _make_tarball(local_dir: str) -> bytes:
    """打包项目代码为 tar.gz (排除 build 产物/依赖大目录)。"""
    buf = io.BytesIO()
    base = Path(local_dir)
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        if base.is_dir():
            for f in base.rglob("*"):
                if not f.is_file():
                    continue
                if set(f.relative_to(base).parts) & _TAR_EXCLUDES:
                    continue
                tf.add(f, arcname=str(f.relative_to(base)))
    return buf.getvalue()


async def _dispatch(target, db, todo_id, source_url) -> None:
    """dispatch_build (立即返回, 记录 BUILD building)。"""
    from arc.application.build.orchestration import BuildOrchestrationService

    await BuildOrchestrationService(db).dispatch_build(
        target, todo_id=todo_id, phase_id=None, source_url=source_url,
    )


async def _background_await(target, todo_id, local_dir, conversation_id) -> None:
    """后台轮询 CI run → 下载产物 → 推 build_complete (独立 db session)。"""
    from arc.application.build.orchestration import BuildOrchestrationService
    from arc.application.execution.stream_manager import stream_manager
    from arc.infrastructure.database import async_session_factory

    try:
        async with async_session_factory() as session:
            await BuildOrchestrationService(session).await_build(
                target, todo_id=todo_id, phase_id=None, local_dir=local_dir,
            )
        await stream_manager.publish_event(
            conversation_id,
            {"event": "build_complete", "build_target": target.value},
        )
    except Exception as exc:
        logger.warning("background await_build failed: %s", exc)
        await stream_manager.publish_event(
            conversation_id,
            {"event": "build_failed", "error": str(exc)},
        )
