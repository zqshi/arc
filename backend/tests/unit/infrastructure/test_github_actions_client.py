"""Tests for infrastructure/ci/github_actions_client — GHA Actions API 封装 (v6.19 T3-e)。

blocked 期不真实联调 (无 token/runner)。用 httpx.MockTransport 注入假响应, 验证
URL 构造 / 请求体 / 响应解析 / 错误传播。client transport 可注入, 生产走真实 HTTP。
"""

import json

import httpx
import pytest

from arc.infrastructure.ci.github_actions_client import GitHubActionsClient


def _client(handler) -> GitHubActionsClient:
    """构造带 MockTransport 的 client (token/owner/repo 固定测试值)。"""
    return GitHubActionsClient(
        "test-token", "acme", "arc", transport=httpx.MockTransport(handler)
    )


class TestDispatchWorkflow:
    async def test_constructs_url_and_body(self):
        """dispatch POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches, body={ref,inputs}。"""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["method"] = request.method
            captured["body"] = json.loads(request.content)
            return httpx.Response(204)

        client = _client(handler)
        await client.dispatch_workflow(
            "build-client-artifacts.yml",
            ref="main",
            inputs={"build_target": "tauri_windows"},
        )
        assert captured["method"] == "POST"
        assert "/repos/acme/arc/actions/workflows/build-client-artifacts.yml/dispatches" in captured["url"]
        assert captured["body"] == {
            "ref": "main",
            "inputs": {"build_target": "tauri_windows"},
        }

    async def test_inputs_optional(self):
        """无 inputs 时 body 仅含 ref。"""

        def handler(request: httpx.Request) -> httpx.Response:
            assert json.loads(request.content) == {"ref": "develop"}
            return httpx.Response(204)

        client = _client(handler)
        await client.dispatch_workflow("wf.yml", ref="develop")

    def test_no_token_raises(self):
        """token 空 → ValueError (CI 编排不可用, 显式报错非静默)。"""
        with pytest.raises(ValueError, match="gha_token"):
            GitHubActionsClient("", "acme", "arc")

    async def test_http_error_raises(self):
        """非 2xx → httpx.HTTPStatusError (orchestration 层捕获转构建失败)。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="forbidden")

        client = _client(handler)
        with pytest.raises(httpx.HTTPStatusError):
            await client.dispatch_workflow("wf.yml")


class TestListRuns:
    async def test_parses_workflow_runs(self):
        """list_runs 解析 workflow_runs 列表 (dispatch 后定位 run_id + 轮询状态)。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {"id": 12345, "status": "completed", "conclusion": "success"},
                        {"id": 12344, "status": "in_progress", "conclusion": None},
                    ]
                },
            )

        client = _client(handler)
        runs = await client.list_runs(event="workflow_dispatch")
        assert len(runs) == 2
        assert runs[0]["id"] == 12345
        assert runs[0]["conclusion"] == "success"

    async def test_empty_runs(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        client = _client(handler)
        assert await client.list_runs() == []


class TestGetRun:
    async def test_constructs_url(self):
        """get_run GET /repos/{owner}/{repo}/actions/runs/{run_id}。"""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json={"id": 99, "status": "in_progress"})

        client = _client(handler)
        run = await client.get_run(99)
        assert run["id"] == 99
        assert "/repos/acme/arc/actions/runs/99" in captured["url"]


class TestListArtifacts:
    async def test_parses_artifacts(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"artifacts": [{"id": 1, "name": "windows-msi"}, {"id": 2, "name": "windows-exe"}]},
            )

        client = _client(handler)
        arts = await client.list_artifacts(12345)
        assert len(arts) == 2
        assert arts[0]["name"] == "windows-msi"


class TestDownloadArtifact:
    async def test_returns_zip_bytes(self):
        """download_artifact GET .../artifacts/{id}/zip, 返回 content bytes。"""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, content=b"PK\x03\x04fake-zip")

        client = _client(handler)
        data = await client.download_artifact(7)
        assert data == b"PK\x03\x04fake-zip"
        assert "/repos/acme/arc/actions/artifacts/7/zip" in captured["url"]
