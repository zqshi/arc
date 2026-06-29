"""CI 构建编排服务 — dispatch_build + await_build 分离 (v6.19 T3-d/T3-g 设计2-3)。

读 target_execution_backend(target), 仅 CI target (windows/ios/harmony) 走本服务;
DOCKER target 走 SandboxRuntime (不经此, T1 决策: CI 编排不进 sandbox 体系)。

分离两段 (CI 异步, 不阻塞 Agent 对话):
- dispatch_build(target, source_url): dispatch workflow + 记录 BUILD(building), 立即返回。
  build 工具调此 → 返回 Agent "构建已派发" → 后台 asyncio task 调 await_build。
- await_build(target, local_dir): 轮询 run 至 completed → 下载 artifact zip → 解压 →
  记录 BUILD(success/failed), 接入 v6.9 BUILD artifact 锚点 (与 docker 产物同走签名/分发)。

blocked 期: 真实构建需 GHA token + windows/macos runner + S3(source_url)。client/
artifact_service 可注入 (测试 mock), 验证 dispatch/await 契约; build 工具 + 后台 task
调度 留 T3-g (需 runner 端到端验证)。
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
import zipfile
from pathlib import Path

from arc.domain.artifact.entity import Artifact
from arc.domain.errors import AppError
from arc.domain.sandbox.execution_backend import (
    BuildExecutionBackend,
    target_execution_backend,
)
from arc.domain.sandbox.value_objects import BuildTarget

logger = logging.getLogger(__name__)

DEFAULT_WORKFLOW = "build-client-artifacts.yml"


class BuildOrchestrationService:
    """编排 CI target 构建 (dispatch → poll → download → BUILD artifact)。"""

    def __init__(self, db, *, client=None, artifact_service=None):
        self._db = db
        self._client = client  # 注入测试; None 时从 settings 构造 (需 gha_token)
        self._artifact_service = artifact_service  # 注入测试; None 时惰性构造

    def _ensure_client(self):
        if self._client is None:
            from arc.config import settings
            from arc.infrastructure.ci import GitHubActionsClient

            self._client = GitHubActionsClient(
                settings.gha_token, settings.gha_owner, settings.gha_repo
            )
        return self._client

    def _ensure_artifact_service(self):
        if self._artifact_service is None:
            from arc.application.artifact.service import ArtifactService

            self._artifact_service = ArtifactService(self._db)
        return self._artifact_service

    async def dispatch_build(
        self,
        target: BuildTarget,
        *,
        todo_id,
        phase_id,
        source_url: str,
        workflow_filename: str = DEFAULT_WORKFLOW,
    ) -> None:
        """dispatch CI 构建 + 记录 BUILD(building), 立即返回 (T3-g 设计2-3, 不阻塞对话)。

        build 工具调此 → 立即返回 Agent "构建已派发" → 后台 asyncio task 调 await_build
        (轮询/下载/记录 success)。dispatch 后 GHA run 创建有延迟, run_id 由 await_build
        内部 list_runs 找最新, 故本方法不返回 run_id。

        Args:
            target: BuildTarget (必须 CI target, 否则 AppError)
            todo_id/phase_id: BUILD artifact 锚点归属
            source_url: 项目代码 tarball URL (CI 下载构建; 调用方上传产生)
            workflow_filename: 触发的 workflow (默认 build-client-artifacts.yml)
        """
        if target_execution_backend(target) != BuildExecutionBackend.CI:
            raise AppError(
                f"BuildOrchestrationService 仅编排 CI target, 收到 {target.value}"
            )

        client = self._ensure_client()
        await client.dispatch_workflow(
            workflow_filename,
            inputs={"build_target": target.value, "source_url": source_url},
        )
        artifact_svc = self._ensure_artifact_service()
        await artifact_svc.create_or_update_build(
            todo_id=todo_id,
            phase_id=phase_id,
            build_target=target.value,
            artifact_path="",
            build_status="building",
        )
        logger.info(
            "CI build dispatched: target=%s workflow=%s", target.value, workflow_filename
        )

    async def await_build(
        self,
        target: BuildTarget,
        *,
        todo_id,
        phase_id,
        local_dir: str,
        poll_interval: float = 10.0,
        poll_timeout: float = 900.0,
    ) -> Artifact:
        """轮询 CI run 至 completed → 下载产物 → 记录 BUILD(success/failed)。

        后台 task 调此 (独立 db session), dispatch_build 之后调。dispatch 后 GHA run
        创建有延迟, 本方法内部 list_runs(event=workflow_dispatch) 找最新 run 轮询。

        Args:
            target: BuildTarget (必须 CI target, 否则 AppError)
            todo_id/phase_id: BUILD artifact 锚点归属
            local_dir: 产物下载解压目标目录 (项目 local_path 下, 调用方传)
            poll_interval/poll_timeout: 轮询 run 间隔/超时 (秒)

        Returns:
            BUILD artifact (build_status=success/failed)
        """
        if target_execution_backend(target) != BuildExecutionBackend.CI:
            raise AppError(
                f"BuildOrchestrationService 仅编排 CI target, 收到 {target.value}"
            )

        client = self._ensure_client()
        run = await self._poll_run(client, poll_interval, poll_timeout)
        artifact_svc = self._ensure_artifact_service()

        if run.get("conclusion") != "success":
            logger.warning(
                "CI build failed: run=%s conclusion=%s",
                run.get("id"),
                run.get("conclusion"),
            )
            return await artifact_svc.create_or_update_build(
                todo_id=todo_id,
                phase_id=phase_id,
                build_target=target.value,
                artifact_path="",
                build_status="failed",
                build_log=f"CI run {run.get('id')} conclusion={run.get('conclusion')}",
            )

        product_path = await self._download_and_extract(client, run["id"], local_dir)
        return await artifact_svc.create_or_update_build(
            todo_id=todo_id,
            phase_id=phase_id,
            build_target=target.value,
            artifact_path=product_path,
            build_status="success",
        )

    async def _poll_run(self, client, interval: float, timeout: float) -> dict:
        """轮询 list_runs(event=workflow_dispatch) 至最新 run completed。

        dispatch 后 GHA run 有创建延迟, 需轮询。status=completed 时返回 (含 conclusion)。
        """
        deadline = time.monotonic() + timeout
        while True:
            runs = await client.list_runs(event="workflow_dispatch", per_page=1)
            if runs:
                run = runs[0]
                if run.get("status") == "completed":
                    return run
            if time.monotonic() >= deadline:
                raise AppError(f"CI 构建轮询超时 ({timeout}s)")
            await asyncio.sleep(interval)

    async def _download_and_extract(
        self, client, run_id: int, local_dir: str
    ) -> str:
        """下载 run 全部 artifact zip 并解压到 local_dir/ci-products。"""
        arts = await client.list_artifacts(run_id)
        if not arts:
            raise AppError(f"CI run {run_id} 无 artifact 可下载")

        product_dir = Path(local_dir) / "ci-products"
        product_dir.mkdir(parents=True, exist_ok=True)
        for art in arts:
            data = await client.download_artifact(art["id"])
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(product_dir)
        return str(product_dir)
