"""分发器后端注册 + 工厂 (v6.2.0 T1)。

与 infrastructure/signer (v6.1) 同构:
- domain 定义 Distributor 接口 + DistributorType
- infrastructure 实现各渠道分发器 (App Store / Play / Tauri updater)
- 本模块注册 DistributorType → Distributor 映射

凭证来源: 项目维度加密存储 (复用 v6.1 crypto 基础设施, 独立 enc_*store_creds 字段)。
load_distribution_creds_for_project(project, channel) 从 project 解密某渠道凭证。
graceful skip: 凭证未配 → upload() 返回 DistributeResult.skip(), 不抛异常。

T2-T4 实现各渠道分发器后, 在 DISTRIBUTORS 注册表填入映射。
"""
from __future__ import annotations

from arc.domain.deployment.distributor import (
    DistributeResult,
    DistributionCredentials,
    Distributor,
    DistributorType,
)
from arc.infrastructure.distributor.appstore import AppStoreDistributor
from arc.infrastructure.distributor.tauri_updater import TauriUpdaterDistributor

__all__ = [
    "DistributeResult",
    "DistributionCredentials",
    "Distributor",
    "DistributorType",
    "get_distributor",
    "load_distribution_creds_for_project",
]


def load_distribution_creds_for_project(
    project, channel: DistributorType
) -> DistributionCredentials:
    """从项目解密某渠道分发凭证 (v6.2.0: 项目维度加密存储)。

    凭证按渠道分字段加密存 Project (enc_appstore_creds 等), 与签名凭证独立。
    未配该渠道 → 返回空 DistributionCredentials。
    """
    from arc.infrastructure.crypto import decrypt

    creds_dict = project.get_distribution_creds(channel, decrypt) or {}

    if channel == DistributorType.APP_STORE:
        return DistributionCredentials(
            appstore_issuer_id=creds_dict.get("appstore_issuer_id", ""),
            appstore_key_id=creds_dict.get("appstore_key_id", ""),
            appstore_api_key=creds_dict.get("appstore_api_key", ""),
        )
    if channel == DistributorType.PLAY_STORE:
        return DistributionCredentials(
            play_key_json=creds_dict.get("play_key_json", ""),
        )
    if channel == DistributorType.TAURI_UPDATER:
        return DistributionCredentials(
            tauri_updater_url=creds_dict.get("tauri_updater_url", ""),
            tauri_updater_secret=creds_dict.get("tauri_updater_secret", ""),
        )
    return DistributionCredentials()


# DistributorType → Distributor 实例注册表
# T2 done: APP_STORE; T4 done: TAURI_UPDATER; T3 待实现 (PLAY_STORE)
DISTRIBUTORS: dict[DistributorType, Distributor] = {
    DistributorType.APP_STORE: AppStoreDistributor(),
    DistributorType.TAURI_UPDATER: TauriUpdaterDistributor(),
}


def get_distributor(distributor_type: DistributorType) -> Distributor | None:
    """按分发渠道返回分发器 (工厂)。

    未注册的渠道 (T2-T4 未实现时) 返回 None — 调用方据此 graceful skip。
    新增渠道时在 DISTRIBUTORS 注册表填入映射。
    """
    return DISTRIBUTORS.get(distributor_type)
