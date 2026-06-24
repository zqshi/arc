"""构建门禁 — 统一校验 build 产物是否就绪，对话/pipeline 两路径共用。

修复: pipeline 的 hooks.trigger_deployment 原先不检查 build_status、只找 dist 目录、
找不到静默 return (三重 graceful-skip)，与对话模式严谨的 PrototypeDeployer 不一致。
本模块抽取共享校验，让两条路径行为一致，且 build 未就绪时硬失败而非静默跳过
(杜绝"pipeline 报成功但 deploy_url 为空"的虚假部署)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class BuildGateError(Exception):
    """构建门禁失败 — build 未就绪，部署不应进行。"""


@dataclass(frozen=True)
class BuildGateResult:
    ok: bool
    reason: str = ""
    build_status: str | None = None

    def ensure_ok(self) -> None:
        """ok=False 时抛 BuildGateError，供调用方在事务内触发回滚。"""
        if not self.ok:
            raise BuildGateError(self.reason)


def check_build_ready(
    *,
    build_status: str | None,
    dist_dir: Path,
    require_non_empty: bool = True,
) -> BuildGateResult:
    """统一构建门禁校验。

    三重检查: build_status == "success" + dist 目录存在 + dist 非空 (防空 build)。
    """
    if build_status != "success":
        return BuildGateResult(
            ok=False,
            reason=f"build_status={build_status!r}，期望 'success'。请先完成构建。",
            build_status=build_status,
        )
    if not dist_dir.is_dir():
        return BuildGateResult(
            ok=False,
            reason=f"构建产物目录不存在: {dist_dir}。请确认构建已执行且产物路径正确。",
            build_status=build_status,
        )
    if require_non_empty and not any(dist_dir.iterdir()):
        return BuildGateResult(
            ok=False,
            reason=f"构建产物目录为空: {dist_dir}。构建可能失败，请检查构建日志。",
            build_status=build_status,
        )
    return BuildGateResult(ok=True, build_status=build_status)
