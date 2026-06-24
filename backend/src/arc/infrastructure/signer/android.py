"""Android 签名器 — apksigner (v6.1.0 T4)。

签名链路:
1. 凭证未配 → SignResult.skip (graceful)
2. apksigner sign --ks {keystore} --ks-pass pass:{ks_pw} --ks-key-alias {alias}
   --key-pass pass:{key_pw} {artifact}
3. 失败 → SignResult.fail

注意: apksigner 在 Android SDK build-tools, 非 macOS/Linux 原生。真实签名需
Android SDK 环境。此处 mock subprocess 验证命令构造 + graceful skip。
Android 签名用 app signing keystore (.jks), 与 Play 上传密钥 (play_key_json,
v6.2 分发层用) 不同 — 本签名器不消费 play_key_json。
"""
from __future__ import annotations

import asyncio
import logging

from arc.domain.deployment.signer import Signer, SignerType, SigningCredentials, SignResult
from arc.infrastructure.signer._cmd import run_cmd

logger = logging.getLogger(__name__)


class AndroidSigner(Signer):
    """Android APK 签名 (apksigner + release keystore)。"""

    signer_type = SignerType.ANDROID

    async def sign(self, artifact_path: str, credentials: SigningCredentials) -> SignResult:
        if not credentials.has_android():
            return SignResult.skip(
                "Android 签名凭证未配全 (需 keystore_path + keystore_password + key_alias)"
            )

        key_pass = credentials.android_key_password or credentials.android_keystore_password
        argv = [
            "apksigner", "sign",
            "--ks", credentials.android_keystore_path,
            "--ks-pass", f"pass:{credentials.android_keystore_password}",
            "--ks-key-alias", credentials.android_key_alias,
            "--key-pass", f"pass:{key_pass}",
            artifact_path,
        ]
        result = await asyncio.to_thread(run_cmd, argv, 300, "apksigner")
        if not result.ok:
            return SignResult.fail(f"apksigner failed: {result.stderr}")
        return SignResult(signed=True, signed_path=artifact_path)
