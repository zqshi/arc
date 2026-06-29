"""构建目标就绪检测 (v6.19 T11 方案3) — 判定每个 BuildTarget 当前是否可投产构建。

前端透出三新平台 (windows/ios/鸿蒙) 时, 未就绪目标灰显并标注原因, 避免用户选了
必失败的目标 (current.md 续3 铁律)。就绪状态由本服务判定, 单一真相源。

判定规则:
- DOCKER target (linux/web/apk): 容器构建无外部依赖, 恒就绪。
- CI target: 需 GHA 凭证 (gha_token) + 云端对象存储 (storage_endpoint/access/secret/
  bucket, 且 endpoint 非 localhost/minio 本地 — T3-g 设计5 硬约束: 本地地址 CI runner
  curl 不到 source_url) 且 runner_kind==HOSTED → 就绪;
  runner_kind==SELF_HOSTED_NEEDED → 需自建工具链 (鸿蒙 DevEco CLT, hosted runner 无);
  凭证缺失 → 未配置 CI 凭证。

分层: domain 只持 runner 特性真相源 (CI_RUNNER_KIND, execution_backend.py); 凭证读取
在 application (settings 属配置, 非 domain 关注); 路由在 interface 暴露查询端点。
"""
from __future__ import annotations

from dataclasses import dataclass

from arc.config import Settings, settings
from arc.domain.sandbox.execution_backend import (
    CI_RUNNER_KIND,
    BuildExecutionBackend,
    CIRunnerKind,
    ci_runner_kind,
    target_execution_backend,
)
from arc.domain.sandbox.value_objects import BuildTarget

# 本地地址特征 — CI hosted runner 不可达 (T3-g 设计5 硬约束)
_LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "minio")


@dataclass(frozen=True)
class TargetReadiness:
    """单个 BuildTarget 的就绪状态。

    ready=True 时 reason 为空; ready=False 时 reason 说明阻塞原因 (前端灰显标注)。
    """

    target: BuildTarget
    ready: bool
    reason: str = ""


def _ci_credentials_ready(s: Settings) -> tuple[bool, str]:
    """CI 构建凭证是否就绪 (GHA token + 云端对象存储)。

    返回 (就绪, 原因); 就绪时原因为空。
    """
    if not s.gha_token:
        return False, "未配置 GitHub Actions 凭证 (ARC_GHA_TOKEN)"
    if (
        not s.storage_endpoint
        or not s.storage_access_key
        or not s.storage_secret_key
        or not s.storage_bucket
    ):
        return False, "未配置云端对象存储 (ARC_STORAGE_*)"
    if any(m in s.storage_endpoint for m in _LOCAL_HOST_MARKERS):
        return False, "对象存储为本地地址, CI runner 不可达 (须云端 ARC_STORAGE_ENDPOINT)"
    return True, ""


def assess_target_readiness(target: BuildTarget, s: Settings | None = None) -> TargetReadiness:
    """判定单个 BuildTarget 的就绪状态。

    s 默认读模块 settings (运行时解析, 便于测试 monkeypatch); 测试可传 fake Settings。
    """
    cfg = s or settings
    backend = target_execution_backend(target)
    if backend is BuildExecutionBackend.DOCKER:
        return TargetReadiness(target, ready=True)
    # CI target: 先凭证, 再 runner 特性
    creds_ok, creds_reason = _ci_credentials_ready(cfg)
    if not creds_ok:
        return TargetReadiness(target, ready=False, reason=creds_reason)
    if ci_runner_kind(target) is CIRunnerKind.SELF_HOSTED_NEEDED:
        return TargetReadiness(target, ready=False, reason="需自建平台 runner/工具链 (DevEco CLT)")
    return TargetReadiness(target, ready=True)


class BuildTargetReadinessService:
    """构建目标就绪检测服务 — 前端就绪状态查询的 application 编排入口。"""

    def __init__(self, s: Settings | None = None) -> None:
        self._s = s or settings

    def list_readiness(self) -> list[TargetReadiness]:
        """列出所有 BuildTarget 的就绪状态 (前端透出/灰显依据)。"""
        return [assess_target_readiness(t, self._s) for t in BuildTarget]


__all__ = [
    "BuildTargetReadinessService",
    "TargetReadiness",
    "assess_target_readiness",
    "CI_RUNNER_KIND",
]
