"""CI 构建编排服务 — 触发 GHA workflow 产物构建, 轮询, 下载, 接入 BUILD artifact (v6.19 T3-d)。

读 target_execution_backend(target), 仅 CI target (windows/ios/harmony) 走本服务;
DOCKER target 走 SandboxRuntime (不经此, T1 决策: CI 编排不进 sandbox 体系)。

链路: dispatch workflow_dispatch → 轮询 run 至 completed → 下载 artifact zip →
解压到本地产物目录 → ArtifactService.create_or_update_build 接入 BUILD artifact 锚点
(v6.9, 与 docker 构建产物同走 签名/分发 链路)。

blocked 期: 真实构建需 GHA token + windows/macos runner。client/artifact_service 可注入
(测试 mock), 验证 dispatch/poll/download/记录 契约; 调用方 (execution_engine 构建入口
拦截 CI target 走本服务) 留 T3-g (需 runner 端到端验证)。
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

    async def orchestrate(
        self,
        target: BuildTarget,
        *,
        todo_id,
        phase_id,
        local_dir: str,
        source_url: str,
        workflow_filename: str = DEFAULT_WORKFLOW,
        poll_interval: float = 10.0,
        poll_timeout: float = 900.0,
    ) -> Artifact:
        """编排 CI target 构建全链路。

        Args:
            target: BuildTarget (必须 CI target, 否则 AppError)
            todo_id/phase_id: BUILD artifact 锚点归属
            local_dir: 产物下载解压目标目录 (项目 local_path 下, 调用方传)
            source_url: 项目代码 tarball URL (CI 下载构建; 调用方 T3-g 上传产生)
            workflow_filename: 触发的 workflow (默认 build-client-artifacts.yml)
            poll_interval/poll_timeout: 轮询 run 间隔/超时 (秒)

        Returns:
            BUILD artifact (build_status=success/failed)
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
        logger.info(
            "CI build dispatched: target=%s workflow=%s", target.value, workflow_filename
        )

        run = await self._poll_run(client, poll_interval, poll_timeout)
        artifact_svc = self._ensure_artifact_service()

        if run.get("conclusion") != "success":
            logger.warning(
                "CI build failed: run=%s conclusion=%s",
                run.get("id"),
                run.get("conclusion"),
            )
            return await artifact_svc.create_or_update_build(
                todo_id,
                phase_id,
                build_target=target.value,
                artifact_path="",
                build_status="failed",
                build_log=f"CI run {run.get('id')} conclusion={run.get('conclusion')}",
            )

        product_path = await self._download_and_extract(client, run["id"], local_dir)
        return await artifact_svc.create_or_update_build(
            todo_id,
            phase_id,
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
