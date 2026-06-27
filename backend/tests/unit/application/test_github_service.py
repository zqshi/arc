"""Unit tests for GitHubService — clone_repo and connect_and_clone methods."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.integration.github_service import GitHubService, parse_repo_url
from arc.domain.errors import AppError
from arc.domain.project.entity import Project


# ── parse_repo_url ──────────────────────────────────────────


class TestParseRepoUrl:
    def test_https_url(self):
        assert parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")

    def test_https_url_with_git_suffix(self):
        assert parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_ssh_url(self):
        assert parse_repo_url("git@github.com:owner/repo.git") == ("owner", "repo")

    def test_invalid_url_returns_none(self):
        assert parse_repo_url("not-a-url") is None

    def test_empty_string_returns_none(self):
        assert parse_repo_url("") is None


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def project():
    return Project(
        name="test-project",
        id=uuid.uuid4(),
        repo_url="https://github.com/acme/widget",
        local_path="",
    )


@pytest.fixture
def project_with_path(project):
    project.local_path = "/existing/path"
    return project


@pytest.fixture
def svc(mock_db):
    svc = GitHubService(mock_db)
    svc.project_repo = AsyncMock()
    svc.todo_repo = AsyncMock()
    return svc


# ── clone_repo ──────────────────────────────────────────────


class TestCloneRepo:
    async def test_clone_selects_default_path_when_none_given(self, svc, project):
        """When target_path is None, uses ~/.arc/repos/{owner}/{repo}."""
        expected_path = str(Path.home() / ".arc" / "repos" / "acme" / "widget")

        with patch("arc.application.integration.github_service.asyncio") as mock_aio:
            mock_aio.to_thread = AsyncMock(return_value="cloned")
            with patch("arc.application.integration.github_service.scan_manager", create=True) as mock_scan:
                mock_scan.is_running.return_value = False
                mock_scan.start_scan = AsyncMock(return_value="task-1")

                # Patch the scan_manager import inside clone_repo
                with patch(
                    "arc.application.project.scan_task.scan_manager", mock_scan,
                ):
                    result = await svc.clone_repo(project)

        assert result["local_path"] == expected_path
        assert result["status"] == "cloned"
        assert project.local_path == expected_path

    async def test_clone_uses_explicit_path(self, svc, project):
        """When target_path is provided, uses that path."""
        with patch("arc.application.integration.github_service.asyncio") as mock_aio:
            mock_aio.to_thread = AsyncMock(return_value="cloned")
            with patch(
                "arc.application.project.scan_task.scan_manager",
            ) as mock_scan:
                mock_scan.is_running.return_value = False
                mock_scan.start_scan = AsyncMock(return_value="task-1")
                result = await svc.clone_repo(project, "/custom/path")

        assert result["local_path"] == "/custom/path"
        assert project.local_path == "/custom/path"

    async def test_clone_invalid_repo_url_raises(self, svc):
        """If repo_url can't be parsed, raises RuntimeError."""
        bad_project = Project(name="bad", repo_url="not-a-url")
        with pytest.raises(AppError, match="无法解析仓库地址"):
            await svc.clone_repo(bad_project)

    async def test_clone_scan_failure_does_not_propagate(self, svc, project):
        """Scan failure after clone doesn't raise — returns scan_started=False."""
        with patch("arc.application.integration.github_service.asyncio") as mock_aio:
            mock_aio.to_thread = AsyncMock(return_value="cloned")
            with patch(
                "arc.application.project.scan_task.scan_manager",
            ) as mock_scan:
                mock_scan.is_running.return_value = False
                mock_scan.start_scan = AsyncMock(side_effect=RuntimeError("scan boom"))
                result = await svc.clone_repo(project)

        assert result["scan_started"] is False
        assert result["status"] == "cloned"


# ── connect_and_clone ───────────────────────────────────────


class TestConnectAndClone:
    async def test_auto_clones_when_no_local_path(self, svc, project):
        """connect_and_clone triggers clone when project.local_path is empty."""
        svc.connect = AsyncMock(return_value={
            "owner": "acme",
            "repo": "widget",
            "full_name": "acme/widget",
            "webhook_secret": "abc123",
        })
        svc.clone_repo = AsyncMock(return_value={
            "status": "cloned",
            "local_path": "/home/.arc/repos/acme/widget",
            "scan_started": True,
        })

        result = await svc.connect_and_clone(project, "ghp_token")

        svc.connect.assert_awaited_once_with(project, "ghp_token")
        svc.clone_repo.assert_awaited_once_with(project)
        assert result["clone_result"]["status"] == "cloned"
        assert result["full_name"] == "acme/widget"

    async def test_skips_clone_when_local_path_exists(self, svc, project_with_path):
        """connect_and_clone does not clone if local_path is already set."""
        svc.connect = AsyncMock(return_value={
            "owner": "acme",
            "repo": "widget",
            "full_name": "acme/widget",
            "webhook_secret": "abc123",
        })
        svc.clone_repo = AsyncMock()

        result = await svc.connect_and_clone(project_with_path, "ghp_token")

        svc.clone_repo.assert_not_awaited()
        assert result["clone_result"] is None

    async def test_clone_failure_returns_error_not_raises(self, svc, project):
        """When clone fails, connect_and_clone catches the error and returns it."""
        svc.connect = AsyncMock(return_value={
            "owner": "acme",
            "repo": "widget",
            "full_name": "acme/widget",
            "webhook_secret": "abc123",
        })
        svc.clone_repo = AsyncMock(side_effect=RuntimeError("network error"))

        result = await svc.connect_and_clone(project, "ghp_token")

        assert result["clone_result"]["status"] == "failed"
        assert "network error" in result["clone_result"]["error"]
        # Connect result is still present
        assert result["full_name"] == "acme/widget"
