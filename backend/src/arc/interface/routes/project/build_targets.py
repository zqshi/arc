"""构建目标就绪状态查询路由 (v6.19 T11 方案3)。

前端透出三新平台 (windows/ios/鸿蒙) 时, 查询此端点获取就绪状态, 未就绪目标灰显标注。
"""
from __future__ import annotations

from fastapi import APIRouter

from arc.application.build.readiness import BuildTargetReadinessService
from arc.interface.deps import CurrentUser
from arc.interface.schemas.project import BuildTargetReadinessResponse

router = APIRouter()


@router.get("/build-targets", response_model=list[BuildTargetReadinessResponse])
async def list_build_target_readiness(
    user: CurrentUser,
) -> list[BuildTargetReadinessResponse]:
    """列出所有构建目标的就绪状态 (前端透出/灰显依据)。

    DOCKER target (linux/web/apk) 恒就绪; CI target 据 CI 凭证 + runner 特性判定
    (hosted runner 凭证齐即就绪; self-hosted 鸿蒙需自建 DevEco 工具链)。
    """
    return BuildTargetReadinessService().list_readiness()
