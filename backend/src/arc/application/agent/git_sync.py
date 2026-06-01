"""Agent 编码完成后的 Git 变更检测与推送。

职责:
- 检测项目目录未提交的变更（git status + diff）
- 生成 diff 预览供用户确认
- 执行 git add → commit → push
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitChanges:
    """Git 变更检测结果。"""

    has_changes: bool = False
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    diff_stat: str = ""
    diff_preview: str = ""  # 前 N 个文件的 patch（截断）


@dataclass
class GitPushResult:
    """Git push 结果。"""

    success: bool = False
    commit_sha: str = ""
    branch: str = ""
    remote_url: str = ""
    files_changed: int = 0
    error: str = ""


async def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    """执行 git 命令并返回 (returncode, stdout, stderr)。"""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


class GitSync:
    """项目目录的 git 变更检测与推送。"""

    def __init__(self, project_path: str) -> None:
        self._path = str(Path(project_path).expanduser().resolve())

    async def is_git_repo(self) -> bool:
        """检查目录是否是 git 仓库。"""
        code, _, _ = await _run_git(["rev-parse", "--is-inside-work-tree"], self._path)
        return code == 0

    async def detect_changes(self) -> GitChanges:
        """检测未提交的变更。"""
        if not await self.is_git_repo():
            return GitChanges()

        # git status --porcelain
        code, stdout, _ = await _run_git(["status", "--porcelain"], self._path)
        if code != 0 or not stdout.strip():
            return GitChanges()

        files = [line[3:] for line in stdout.strip().splitlines() if len(line) > 3]

        # git diff --stat (staged + unstaged)
        _, stat_out, _ = await _run_git(["diff", "--stat", "HEAD"], self._path)
        # 如果没有 HEAD commit（新仓库），用 diff --stat --cached
        if not stat_out.strip():
            _, stat_out, _ = await _run_git(["diff", "--stat", "--cached"], self._path)

        # 解析 insertions/deletions
        insertions = deletions = 0
        for line in stat_out.splitlines():
            if "insertion" in line or "deletion" in line:
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "insertion" in part:
                        try:
                            insertions = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    if "deletion" in part:
                        try:
                            deletions = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass

        # diff preview (前 5 个文件的 patch，限 3000 字符)
        preview_files = files[:5]
        _, diff_out, _ = await _run_git(
            ["diff", "HEAD", "--", *preview_files], self._path
        )
        if not diff_out.strip():
            _, diff_out, _ = await _run_git(
                ["diff", "--cached", "--", *preview_files], self._path
            )

        diff_preview = diff_out[:3000]
        if len(diff_out) > 3000:
            diff_preview += f"\n\n... (truncated, {len(diff_out)} chars total)"

        return GitChanges(
            has_changes=True,
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
            diff_stat=stat_out.strip(),
            diff_preview=diff_preview,
        )

    async def commit_and_push(
        self,
        message: str,
        branch: str | None = None,
    ) -> GitPushResult:
        """git add -A → commit → push。

        Args:
            message: commit message
            branch: 目标分支（None = 当前分支）
        """
        if not await self.is_git_repo():
            return GitPushResult(error="Not a git repository")

        # Ensure user config
        await self._ensure_git_user()

        # git add -A
        code, _, stderr = await _run_git(["add", "-A"], self._path)
        if code != 0:
            return GitPushResult(error=f"git add failed: {stderr}")

        # git commit
        code, stdout, stderr = await _run_git(
            ["commit", "-m", message], self._path
        )
        if code != 0:
            if "nothing to commit" in stdout or "nothing to commit" in stderr:
                return GitPushResult(error="Nothing to commit")
            return GitPushResult(error=f"git commit failed: {stderr}")

        # Get commit SHA
        _, sha_out, _ = await _run_git(["rev-parse", "HEAD"], self._path)
        commit_sha = sha_out.strip()

        # Get current branch
        _, branch_out, _ = await _run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], self._path
        )
        current_branch = branch_out.strip()
        target_branch = branch or current_branch

        # Get remote URL
        _, remote_out, _ = await _run_git(
            ["remote", "get-url", "origin"], self._path
        )
        remote_url = remote_out.strip()

        # git push
        push_args = ["push", "origin", target_branch]
        code, stdout, stderr = await _run_git(push_args, self._path)
        if code != 0:
            # push 失败但 commit 已创建
            return GitPushResult(
                success=False,
                commit_sha=commit_sha,
                branch=target_branch,
                remote_url=remote_url,
                error=f"git push failed: {stderr}. Commit created locally.",
            )

        # Count files changed
        _, numstat, _ = await _run_git(
            ["diff", "--stat", "HEAD~1..HEAD"], self._path
        )
        files_count = len([l for l in numstat.splitlines() if l.strip() and "changed" not in l])

        logger.info(
            "Git push success: %s → %s/%s (%d files)",
            commit_sha[:8], remote_url, target_branch, files_count,
        )

        return GitPushResult(
            success=True,
            commit_sha=commit_sha,
            branch=target_branch,
            remote_url=remote_url,
            files_changed=files_count,
        )

    async def _ensure_git_user(self) -> None:
        """确保 git user.name 和 user.email 已配置。"""
        code, _, _ = await _run_git(["config", "user.name"], self._path)
        if code != 0:
            await _run_git(["config", "user.name", "Arc Agent"], self._path)
            await _run_git(["config", "user.email", "arc-agent@local"], self._path)
