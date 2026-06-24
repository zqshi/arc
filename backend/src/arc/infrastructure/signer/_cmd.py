"""签名器命令执行公共工具 (v6.1.0)。

三平台签名器 (Apple/Windows/Android) 共用 subprocess 同步执行 + 结果封装。
复用 sandbox/runtime.py 的 subprocess.run + asyncio.to_thread 风格。
"""
from __future__ import annotations

import subprocess


class CmdResult:
    """命令执行结果 (签名器内部用)。"""

    __slots__ = ("ok", "stdout", "stderr")

    def __init__(self, ok: bool, stdout: str, stderr: str):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr


def run_cmd(argv: list[str], timeout: int = 600, tool_name: str = "签名工具") -> CmdResult:
    """同步执行签名命令, 返回 CmdResult。

    tool_name 用于 FileNotFoundError 时的错误提示 (如 "signtool 未安装")。
    timeout/tool_name 为位置可选参数, 便于 asyncio.to_thread 直接透传。
    """
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return CmdResult(ok=r.returncode == 0, stdout=r.stdout, stderr=r.stderr.strip())
    except FileNotFoundError:
        return CmdResult(ok=False, stdout="", stderr=f"{tool_name} 未安装")
    except subprocess.TimeoutExpired:
        return CmdResult(ok=False, stdout="", stderr=f"{tool_name} 执行超时")
