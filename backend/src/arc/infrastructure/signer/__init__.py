"""签名器后端注册 + 工厂 (v6.1.0 T1)。

与 infrastructure/deployer/get_deployer 同构:
- domain 定义 Signer 接口 + SignerType
- infrastructure 实现各平台签名器 (Apple/Windows/Android)
- 本模块注册 SignerType → Signer 映射

凭证来源 (v6.1.0 修正): 项目维度加密存储, 非全局 config。
load_credentials_for_project(project, platform) 从 project 解密某平台凭证。
graceful skip: 凭证未配 → sign() 返回 SignResult.skip(), 不抛异常。

T2-T4 实现各平台签名器后, 在 SIGNERS 注册表填入映射。
"""
from __future__ import annotations

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
    "load_credentials_for_project",
]


def load_credentials_for_project(project, platform: SignerType) -> SigningCredentials:
    """从项目解密某平台签名凭证 (v6.1.0: 项目维度加密存储)。

    凭证按平台分字段加密存 Project (enc_apple_creds 等)。
    加解密通过 infrastructure/crypto 注入。未配该平台 → 返回空 SigningCredentials。
    """
    from arc.infrastructure.crypto import decrypt

    creds_dict = project.get_signing_creds(platform, decrypt) or {}

    if platform == SignerType.APPLE:
        return SigningCredentials(
            apple_dev_id=creds_dict.get("apple_dev_id", ""),
            apple_team_id=creds_dict.get("apple_team_id", ""),
        )
    if platform == SignerType.WINDOWS:
        return SigningCredentials(
            win_ev_cert_path=creds_dict.get("win_ev_cert_path", ""),
            win_ev_password=creds_dict.get("win_ev_password", ""),
        )
    if platform == SignerType.ANDROID:
        return SigningCredentials(
            play_key_json=creds_dict.get("play_key_json", ""),
        )
    return SigningCredentials()


# SignerType → Signer 实例注册表
# T2-T4 实现后填充: APPLE → AppleSigner / WINDOWS → WindowsSigner / ANDROID → AndroidSigner
SIGNERS: dict[SignerType, Signer] = {}


def get_signer(signer_type: SignerType) -> Signer | None:
    """按签名平台返回签名器 (工厂)。

    未注册的 signer_type (T2-T4 未实现时) 返回 None — 调用方据此 graceful skip。
    新增平台时在 SIGNERS 注册表填入映射。
    """
    return SIGNERS.get(signer_type)
