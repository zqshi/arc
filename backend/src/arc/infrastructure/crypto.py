"""Fernet 对称加密工具 (v6.1.0)。

签名凭证 (Apple 私钥 / Windows EV 证书 / Play JSON) 是高敏感数据, 不能明文存 DB。
本模块提供对称加解密, 密钥从 config.signing_secret_key 取 (Fernet key)。

降级原则: signing_secret_key 未配 (dev 环境) → _fernet() 返回 None,
encrypt/decrypt 退化为 identity (明文)。避免 dev 启动阻断, 但 .env.example
注释明确生产必配。既有 github_token 明文存储问题不在本版本修复, 但本模块
为后续加密 github_token 留基础设施。

被 application 层调用, 注入 domain 实体 (避免 domain→infrastructure 违规)。
"""
from __future__ import annotations

import logging

from arc.config import settings

logger = logging.getLogger(__name__)


def _fernet():
    """按 config.signing_secret_key 构造 Fernet, 空密钥返回 None (降级 identity)。"""
    key = getattr(settings, "signing_secret_key", "") or ""
    if not key:
        return None
    from cryptography.fernet import Fernet

    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """加密明文 → base64 token。空输入/空密钥 → 原样返回。"""
    if not plaintext:
        return ""
    f = _fernet()
    if f is None:
        logger.warning("signing_secret_key 未配置, 凭证以明文存储 (仅 dev 可接受)")
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """解密 token → 明文。空输入/空密钥 → 原样返回; 非法 token → 空串。"""
    if not token:
        return ""
    f = _fernet()
    if f is None:
        return token  # identity
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        # 非法 token (非 Fernet 格式/被篡改) → 当作未配凭证
        return ""
