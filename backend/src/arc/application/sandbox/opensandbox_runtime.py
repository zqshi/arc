"""OpenSandbox 云沙箱运行时 (v6.7 波次3)。

远程沙箱后端, 对接 opensandbox-group/OpenSandbox (Python SDK)。沙箱即工作区
模式: 项目初始化上传到沙箱, read/write/run 全在沙箱内执行, 保证一致性
(远程沙箱无法挂载本地 project_path, 故 read 类也走沙箱)。

沙箱惰性创建: 首次工具调用时 Sandbox.create + 上传项目; 按 conversation
长驻, close 时释放。多 worker 下靠 sticky session (nginx 按 conversation_id
哈希路由 WS), runtime 在持有它的 worker 长驻。

API (opensandbox SDK):
- Sandbox.create(image, *, timeout, env, entrypoint) → Sandbox
- sandbox.commands.run(command) → Execution (logs.stdout[].text)
- sandbox.files.read_file(path) → str
- sandbox.files.write_files([WriteEntry(path, data, mode)])
- sandbox.close()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from opensandbox import Sandbox
from opensandbox.models import WriteEntry

from arc.application.sandbox.runtime import SandboxRuntime
from arc.domain.sandbox.value_objects import SandboxPolicy

logger = logging.getLogger(__name__)

# 上传时跳过的目录 (与 tools._list_directory 一致)
_SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "dist", "build", ".venv", "venv",
    ".pytest_cache", ".ruff_cache", "target",
}
_DEFAULT_IMAGE = "python:3.12-slim"
_UPLOAD_MAX_BYTES = 512 * 1024  # 单文件上传上限 512KB (大文件如 lock 跳过)


class OpenSandboxRuntime(SandboxRuntime):
    """OpenSandbox 云沙箱运行时 — 沙箱即工作区。"""

    def __init__(
        self,
        policy: SandboxPolicy,
        project_path: str,
        conversation_id: str,
        *,
        image: str = _DEFAULT_IMAGE,
        server_url: str = "",
        api_key: str = "",
        timeout_seconds: int = 600,
    ):
        self._policy = policy
        self._project_path = Path(project_path).expanduser().resolve()
        self._conversation_id = conversation_id
        self._image = image
        self._server_url = server_url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._sandbox: Sandbox | None = None
        self._upload_done = False

    def _sandbox_path(self, rel: str) -> str:
        """相对项目路径 → 沙箱绝对路径 (项目统一上传到 /workspace)。"""
        return "/workspace/" + rel.lstrip("/")

    async def _ensure_sandbox(self) -> Sandbox:
        """惰性创建沙箱 + 首次上传项目。"""
        if self._sandbox is not None:
            return self._sandbox

        import datetime as dt

        logger.info(
            "Creating OpenSandbox for conv=%s image=%s",
            self._conversation_id, self._image,
        )
        self._sandbox = await Sandbox.create(
            self._image,
            timeout=dt.timedelta(seconds=self._timeout_seconds),
        )
        await self._upload_project()
        return self._sandbox

    async def _upload_project(self) -> None:
        """把项目目录上传到沙箱 (批量 write_files)。

        跳过 node_modules/.git 等目录与大文件。MVP 用逐文件上传; 大项目
        后续优化为 tar 上传或 PVC 预置。
        """
        if self._upload_done or self._sandbox is None:
            return

        entries: list[WriteEntry] = []
        for path in self._iter_project_files():
            try:
                data = path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.debug("Skip upload %s: %s", path, exc)
                continue
            rel = path.relative_to(self._project_path).as_posix()
            entries.append(WriteEntry(path=self._sandbox_path(rel), data=data))
            if len(entries) >= 100:  # 分批避免单次过大
                await self._sandbox.files.write_files(entries)
                entries.clear()

        if entries:
            await self._sandbox.files.write_files(entries)
        self._upload_done = True
        logger.info(
            "Project uploaded to sandbox conv=%s", self._conversation_id
        )

    def _iter_project_files(self):
        """遍历项目文件 (跳过 _SKIP_DIRS + 大文件)。"""
        if not self._project_path.exists():
            return
        for path in self._project_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            try:
                if path.stat().st_size > _UPLOAD_MAX_BYTES:
                    continue
            except OSError:
                continue
            yield path

    async def run_command(self, params: dict) -> str:
        sb = await self._ensure_sandbox()
        command = params["command"]
        execution = await sb.commands.run(command)
        return self._format_execution(execution, command)

    async def write_file(self, params: dict) -> str:
        sb = await self._ensure_sandbox()
        rel = params["path"]
        content = params["content"]
        await sb.files.write_files([WriteEntry(path=self._sandbox_path(rel), data=content)])
        return f"已写入(云沙箱): {rel} ({len(content)} 字符)"

    async def read_file(self, params: dict) -> str:
        """从沙箱读文件 (沙箱即工作区, 不读本地 project_path)。"""
        sb = await self._ensure_sandbox()
        rel = params["path"]
        start_line = params.get("start_line", 1)
        end_line = params.get("end_line")
        try:
            content = await sb.files.read_file(self._sandbox_path(rel))
        except Exception as exc:
            return f"错误: 读取失败 — {rel}: {exc}"

        lines = content.splitlines()
        total = len(lines)
        s = max(0, start_line - 1)
        e = min(total, end_line) if end_line else min(s + 500, total)
        selected = lines[s:e]
        header = f"文件: {rel} ({total} 行, 显示 {s + 1}-{e})\n"
        numbered = "".join(
            f"{s + i + 1:4d} | {line}" for i, line in enumerate(selected)
        )
        if e < total:
            numbered += f"\n... 还有 {total - e} 行未显示，使用 start_line={e + 1} 继续阅读"
        return header + numbered

    async def list_directory(self, params: dict) -> str:
        """沙箱内列目录 (经 run_command 调 ls)。"""
        sb = await self._ensure_sandbox()
        rel = params.get("path", ".")
        target = "/workspace" if rel == "." else self._sandbox_path(rel)
        execution = await sb.commands.run(
            f"ls -la {target} 2>/dev/null || ls {target}"
        )
        return self._format_execution(execution, f"ls {target}")

    async def grep_search(self, params: dict) -> str:
        """沙箱内 grep 搜索。"""
        sb = await self._ensure_sandbox()
        pattern = params["pattern"]
        include = params.get("include", "")
        cmd = "grep -rn --color=never -I"
        if include:
            cmd += f" --include='{include}'"
        for skip in _SKIP_DIRS:
            cmd += f" --exclude-dir={skip}"
        cmd += f" '{pattern}' /workspace"
        execution = await sb.commands.run(cmd)
        return self._format_execution(execution, cmd)

    def _format_execution(self, execution: Any, command: str) -> str:
        """从 Execution 提取 stdout/stderr 格式化 (对齐 tools._run_command 输出)。"""
        stdout = stderr = ""
        exit_code = 0
        try:
            logs = execution.logs
            stdout = "".join(
                m.text for m in (logs.stdout or [])
            )
            stderr = "".join(
                m.text for m in (logs.stderr or [])
            )
            if hasattr(execution, "result") and execution.result:
                exit_code = getattr(execution.result, "exit_code", 0) or 0
        except Exception as exc:
            logger.warning("Format execution failed: %s", exc)

        parts: list[str] = []
        if stdout:
            stdout = stdout[:10000]
            if len(stdout) > 10000:
                stdout += "\n... stdout 已截断"
            parts.append(stdout)
        if stderr:
            stderr = stderr[:5000]
            if len(stderr) > 5000:
                stderr += "\n... stderr 已截断"
            parts.append(f"[stderr]\n{stderr}")
        if exit_code != 0:
            parts.append(f"[exit code: {exit_code}]")
        return "\n".join(parts) if parts else "(无输出)"

    async def close(self) -> None:
        if self._sandbox is not None:
            try:
                await self._sandbox.close()
            except Exception as exc:
                logger.warning("Sandbox close failed: %s", exc)
            self._sandbox = None
            self._upload_done = False
