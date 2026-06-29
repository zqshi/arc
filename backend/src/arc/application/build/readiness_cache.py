"""就绪检测探活结果缓存 (v6.19 续6 补丁3) — 进程内轻量缓存。

探活 (GHA verify_token + storage head_bucket) 是秒级网络调用, 不应每次读就绪端点都跑。
缓存探活结果 + TTL, 端点读缓存 (毫秒), 后台 task 定时/惰性刷新写缓存。

进程内 dict 缓存 (无外部依赖): dev 单进程足够; 多 worker 部署各 worker 独立缓存
(探活是 UI 辅助非精确门禁, 短暂不一致可接受)。线程安全靠 GIL (dict 单操作原子)。
"""
from __future__ import annotations

import time

from arc.domain.sandbox.value_objects import BuildTarget

# 探活结果缓存: target -> (verified_ok, timestamp)
_cache: dict[BuildTarget, tuple[bool, float]] = {}

TTL_SECONDS = 300  # 5 分钟, 平衡时效与 GHA 速率消耗


def get_cached_verify(target: BuildTarget) -> bool | None:
    """读缓存探活结果。

    命中且未过 TTL → 返回 bool; 过期/未命中 → None (调用方触发后台刷新, 本次乐观判 ready)。
    """
    entry = _cache.get(target)
    if entry is None:
        return None
    ok, ts = entry
    if time.monotonic() - ts > TTL_SECONDS:
        return None  # 过期
    return ok


def set_cached_verify(target: BuildTarget, ok: bool) -> None:
    """写探活结果缓存 (后台 task 调用)。"""
    _cache[target] = (ok, time.monotonic())


def clear_cache() -> None:
    """清空缓存 (测试用)。"""
    _cache.clear()
