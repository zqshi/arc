"""构建目标就绪检测 (v6.19 T11 方案3) — 判定每个 BuildTarget 当前是否可投产构建。

前端透出三新平台 (windows/ios/鸿蒙) 时, 未就绪目标灰显并标注原因, 避免用户选了
必失败的目标 (current.md 续3 铁律)。就绪状态由本服务判定, 单一真相源。

判定规则 (两维度叠加):
- 静态就绪 (快, 读 settings): DOCKER target 恒就绪; CI target 需 GHA 凭证
  (gha_token) + 云端对象存储 (storage_*, endpoint 非本地) 且 runner_kind==HOSTED;
  SELF_HOSTED_NEEDED (鸿蒙 DevEco) 仍 blocked; 凭证缺失 blocked。
- 探活就绪 (慢, 缓存): 凭证真实有效 (GHA token GET /user 通 + S3 head_bucket 通),
  结果带 TTL 缓存 (readiness_cache), 端点读缓存后台刷新。verified=None (未探活/
  过期) 时乐观判 ready (避免误灰显可用目标); verified=False 时 blocked (凭证探活失败)。

分层: domain 只持 runner 特性真相源 (CI_RUNNER_KIND); 探活在 infrastructure (GHA
verify_token / storage verify); 缓存+编排在 application; settings 属配置非 domain 关注。
"""
from __future__ import annotations

import asyncio
import logging
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

from .readiness_cache import get_cached_verify, set_cached_verify

logger = logging.getLogger(__name__)

# 本地地址特征 — CI hosted runner 不可达 (T3-g 设计5 硬约束)
_LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "minio")


@dataclass(frozen=True)
class TargetReadiness:
    """单个 BuildTarget 的就绪状态。

    ready=True 时 reason 为空; ready=False 时 reason 说明阻塞原因 (前端灰显标注)。
    verified: 探活结果 (None=未探活/过期, True=探活通过, False=探活失败);
    verified_at: 探活时间戳 (ISO), 仅 verified 非 None 时有值。
    """

    target: BuildTarget
    ready: bool
    reason: str = ""
    verified: bool | None = None
    verified_at: str | None = None


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
    """判定单个 BuildTarget 的就绪状态 (静态 + 缓存探活)。

    s 默认读模块 settings (运行时解析, 便于测试 monkeypatch); 测试可传 fake Settings。
    探活结果读缓存 (无网络调用); 缓存空/过期返回 verified=None (乐观判 ready)。
    """
    cfg = s or settings
    backend = target_execution_backend(target)
    if backend is BuildExecutionBackend.DOCKER:
        return TargetReadiness(target, ready=True)
    # CI target: 先静态凭证, 再 runner 特性, 最后缓存探活
    creds_ok, creds_reason = _ci_credentials_ready(cfg)
    if not creds_ok:
        return TargetReadiness(target, ready=False, reason=creds_reason)
    if ci_runner_kind(target) is CIRunnerKind.SELF_HOSTED_NEEDED:
        return TargetReadiness(target, ready=False, reason="需自建平台 runner/工具链 (DevEco CLT)")
    # 静态齐 + hosted: 读探活缓存组合 ready
    verified = get_cached_verify(target)
    if verified is False:
        return TargetReadiness(
            target, ready=False, reason="CI 凭证探活失败, 请检查有效性 (token 权限/存储可达)",
            verified=False,
        )
    return TargetReadiness(target, ready=True, verified=verified)


async def refresh_verifications(s: Settings | None = None) -> None:
    """后台探活刷新: 对静态齐的 hosted CI target 探活 (GHA token + S3), 写缓存。

    GHA verify_token + storage verify 并发; 多 target 间并发。失败写 False (凭证探活失败),
    不抛 (fire-and-forget 后台 task)。SELF_HOSTED / 静态不齐的 target 跳过 (无意义)。
    """
    cfg = s or settings
    from arc.infrastructure.ci.github_actions_client import GitHubActionsClient
    from arc.infrastructure.storage import get_storage

    targets = [
        t for t in BuildTarget
        if target_execution_backend(t) is BuildExecutionBackend.CI
        and _ci_credentials_ready(cfg)[0]
        and ci_runner_kind(t) is CIRunnerKind.HOSTED
    ]
    if not targets:
        return

    # GHA token 探活 (所有 hosted CI target 共用同一 token, 探一次即可)
    gha_ok = False
    try:
        client = GitHubActionsClient(token=cfg.gha_token, owner="", repo="")
        gha_ok = await client.verify_token()
    except Exception:  # noqa: BLE001
        gha_ok = False

    storage_ok = False
    try:
        storage_ok = get_storage().verify()
    except Exception:  # noqa: BLE001
        storage_ok = False

    # GHA + S3 两者皆通才算凭证有效 (source_url 依赖 S3, dispatch 依赖 GHA)
    verified = gha_ok and storage_ok
    for t in targets:
        set_cached_verify(t, verified)
    logger.info("就绪探活刷新完成: %d target, verified=%s (gha=%s storage=%s)",
                len(targets), verified, gha_ok, storage_ok)


def trigger_background_refresh(s: Settings | None = None) -> None:
    """触发后台探活刷新 (fire-and-forget, 不阻塞调用方)。

    端点首次被调/手动 ?refresh 时触发; asyncio.create_task 起后台 task 立即返回。
    无返回值 — 调用方不等待探活完成 (读缓存, 下次端点调用见新结果)。
    """
    asyncio.create_task(refresh_verifications(s))


class BuildTargetReadinessService:
    """构建目标就绪检测服务 — 前端就绪状态查询的 application 编排入口。"""

    def __init__(self, s: Settings | None = None) -> None:
        self._s = s or settings

    def list_readiness(self) -> list[TargetReadiness]:
        """列出所有 BuildTarget 的就绪状态 (前端透出/灰显依据, 读缓存无网络)。"""
        return [assess_target_readiness(t, self._s) for t in BuildTarget]


__all__ = [
    "BuildTargetReadinessService",
    "TargetReadiness",
    "assess_target_readiness",
    "refresh_verifications",
    "trigger_background_refresh",
    "CI_RUNNER_KIND",
]

