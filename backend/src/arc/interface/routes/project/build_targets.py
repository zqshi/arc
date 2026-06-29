"""构建目标就绪状态查询路由 (v6.19 T11 方案3 + 续6 探活缓存)。

前端透出三新平台 (windows/ios/鸿蒙) 时, 查询此端点获取就绪状态, 未就绪目标灰显标注。
端点读缓存 (毫秒, 无网络); 探活在后台 task 刷新 (惰性触发 + ?refresh 手动触发)。
"""
from __future__ import annotations

from fastapi import APIRouter

from arc.application.build.readiness import (
    BuildTargetReadinessService,
    trigger_background_refresh,
)
from arc.application.build.readiness_cache import _cache
from arc.interface.deps import CurrentUser
from arc.interface.schemas.project import BuildTargetReadinessResponse

router = APIRouter()


@router.get("/build-targets", response_model=list[BuildTargetReadinessResponse])
async def list_build_target_readiness(
    user: CurrentUser,
    refresh: bool = False,
) -> list[BuildTargetReadinessResponse]:
    """列出所有构建目标的就绪状态 (前端透出/灰显依据, 读缓存无网络)。

    DOCKER target (linux/web/apk) 恒就绪; CI target 据静态凭证 + runner 特性 + 缓存探活判定。
    首次缓存空时惰性触发后台探活刷新 (本次返回 verified=null 乐观判 ready, 下次见新结果);
    ?refresh=true 手动触发后台刷新 (填完凭证后主动刷新, 不阻塞返回)。
    """
    if refresh or not _cache:
        trigger_background_refresh()
    return BuildTargetReadinessService().list_readiness()

