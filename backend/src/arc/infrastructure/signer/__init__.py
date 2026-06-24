"""签名器后端注册 + 工厂 (v6.1.0 T1)。

与 infrastructure/deployer/get_deployer 同构:
- domain 定义 Signer 接口 + SignerType
- infrastructure 实现各平台签名器 (Apple/Windows/Android)
- 本模块注册 SignerType → Signer 映射

凭证从 config.Settings 加载为 SigningCredentials, 注入签名器。
graceful skip: 凭证未配 → sign() 返回 SignResult.skip(), 不抛异常。

T2-T4 实现各平台签名器后, 在 SIGNERS 注册表填入映射。
"""
from __future__ import annotations

from arc.config import settings
from arc.domain.deployment.signer import (
    SignResult,
    SigningCredentials,
    Signer,
    SignerType,
)

__all__ = [
    "SignResult",
    "SigningCredentials",
    "Signer",
    "SignerType",
    "get_signer",
    "load_credentials",
]


def load_credentials() -> SigningCredentials:
    """从 config.Settings 加载签名凭证 (聚合三平台)。"""
    return SigningCredentials(
        apple_dev_id=settings.apple_dev_id,
        apple_team_id=settings.apple_team_id,
        win_ev_cert_path=settings.win_ev_cert_path,
        win_ev_password=settings.win_ev_password,
        play_key_json=settings.play_key_json,
    )


# SignerType → Signer 实例注册表
# T2-T4 实现后填充: APPLE → AppleSigner / WINDOWS → WindowsSigner / ANDROID → AndroidSigner
SIGNERS: dict[SignerType, Signer] = {}


def get_signer(signer_type: SignerType) -> Signer | None:
    """按签名平台返回签名器 (工厂)。

    未注册的 signer_type (T2-T4 未实现时) 返回 None — 调用方据此 graceful skip。
    新增平台时在 SIGNERS 注册表填入映射。
    """
    return SIGNERS.get(signer_type)
