"""GitHub Actions API client — CI 编排触发/轮询/下载产物 (v6.19 T3-e)。

为 BuildOrchestrationService (application/build/orchestration.py) 提供 GHA Actions
API 封装: 触发 workflow_dispatch、轮询 run 状态、下载 artifact。与
infrastructure/github_client.py (Issue/PR 协作域) 分模块 — Actions 是 CI 构建编排域。

blocked 期约束: 真实调用需 GHA token (actions:write) + windows/macos runner。本
client 封装 HTTP 调用, 单测用 httpx.MockTransport 注入假响应验证 URL 构造与状态解析
(不真实联调)。token/owner/repo 从 config.Settings 读 (gha_token/gha_owner/gha_repo)。

设计: 每次 HTTP 调用独立创建 AsyncClient (无持久 client), 避免跨请求生命周期管理;
CI 编排低频 (分钟级), 新建开销可忽略。follow_redirects=True 处理 download_artifact
的重定向 (api.github.com → actions.githubusercontent.com)。transport 可注入 (测试)。
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubActionsClient:
    """GHA Actions API client — workflow 编排 (dispatch/poll/download)。

    错误: HTTP 非 2xx 抛 httpx.HTTPStatusError (orchestration 层捕获转构建失败状态)。
    """

    def __init__(
        self,
        token: str,
        owner: str,
        repo: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        if not token:
            raise ValueError(
                "gha_token 未配 — CI 编排需 GHA token (actions:write 权限)"
            )
        self._token = token
        self._owner = owner
        self._repo = repo
        self._transport = transport  # 测试注入 MockTransport; 生产 None 走真实 HTTP

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict = {
            "base_url": API_BASE,
            "headers": self._headers(),
            "timeout": 30.0,
            "follow_redirects": True,  # download_artifact 重定向到临时下载 URL
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def dispatch_workflow(
        self,
        workflow_filename: str,
        ref: str = "main",
        inputs: dict | None = None,
    ) -> None:
        """触发 workflow_dispatch。GHA API 不直接返回 run_id, 需轮询 list_runs 定位。

        Args:
            workflow_filename: workflow 文件名 (如 "build-client-artifacts.yml")
            ref: 触发分支 (默认 main)
            inputs: workflow inputs (如 {"build_target": "tauri_windows"})
        """
        body: dict = {"ref": ref}
        if inputs:
            body["inputs"] = inputs
        async with self._client() as client:
            resp = await client.post(
                f"/repos/{self._owner}/{self._repo}/actions/workflows/"
                f"{workflow_filename}/dispatches",
                json=body,
            )
            resp.raise_for_status()  # 204 No Content

    async def list_runs(
        self,
        *,
        event: str | None = None,
        per_page: int = 1,
    ) -> list[dict]:
        """列出 workflow runs (默认最新 1 条)。dispatch 后定位 run_id + 轮询状态用。

        返回 run dict 列表 (含 id/status/conclusion)。status: queued/in_progress/
        completed; conclusion: success/failure/cancelled (仅 completed 时有意义)。
        """
        params: dict = {"per_page": per_page}
        if event:
            params["event"] = event
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self._owner}/{self._repo}/actions/runs", params=params,
            )
            resp.raise_for_status()
            return resp.json().get("workflow_runs", [])

    async def get_run(self, run_id: int) -> dict:
        """查询单个 run 状态 (轮询构建进度用)。"""
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self._owner}/{self._repo}/actions/runs/{run_id}",
            )
            resp.raise_for_status()
            return resp.json()

    async def list_artifacts(self, run_id: int) -> list[dict]:
        """列出 run 的 artifacts (含 id/name, 供 download_artifact 用)。"""
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self._owner}/{self._repo}/actions/runs/{run_id}/artifacts",
            )
            resp.raise_for_status()
            return resp.json().get("artifacts", [])

    async def download_artifact(self, artifact_id: int) -> bytes:
        """下载 artifact zip 内容 (GHA 重定向到临时下载 URL, follow_redirects=True)。"""
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self._owner}/{self._repo}/actions/artifacts/"
                f"{artifact_id}/zip",
            )
            resp.raise_for_status()
            return resp.content

    async def verify_token(self) -> bool:
        """探活: GET /user 验 token 有效 (v6.19 续6 就绪检测探活)。

        2xx→True (token 有效未失效), 4xx/异常→False。
        边界: 只验 token 有效不验 actions:write 权限 (GET /user 不返权限),
        权限不足在真实 dispatch 时暴露 (错误信息明确)。
        """
        try:
            async with self._client() as client:
                resp = await client.get("/user")
                return resp.status_code < 400
        except Exception:  # noqa: BLE001 — 探活容错, 任何网络/解析异常均判无效
            return False
