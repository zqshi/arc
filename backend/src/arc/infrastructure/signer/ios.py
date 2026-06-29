"""iOS 签名器 — security import + codesign (v6.19 T7)。

签名链路:
1. 凭证未配 → SignResult.skip (graceful, 不阻断构建)
2. security import {p12} -P {pwd} -k login.keychain -T /usr/bin/codesign  (导入 .p12 证书)
3. codesign --force --sign {identity} {artifact}  (重签 .ipa/.app)
4. 任一失败 → SignResult.fail (signed=False, 不抛异常)

注意: 真实签名需 macOS + 钥匙串 + provisioning profile。此处 mock subprocess
验证命令构造 + graceful skip, 与 WindowsSigner 同构 (v6.1 mock 先行模式)。
provisioning profile 嵌入 (.app/embedded.mobileprovision) 属文件操作, 本骨架
聚焦 codesign 命令构造; profile 字段留作分发层消费 (真实接入时由 runner 处理)。
"""
from __future__ import annotations

import asyncio
import logging

from arc.domain.deployment.signer import Signer, SignerType, SigningCredentials, SignResult
from arc.infrastructure.signer._cmd import run_cmd

logger = logging.getLogger(__name__)

# 导入证书的目标 keychain (macOS 用户登录钥匙串)
_KEYCHAIN = "~/Library/Keychains/login.keychain"


class IosSigner(Signer):
    """iOS .ipa 签名 (security import + codesign)。"""

    signer_type = SignerType.IOS

    async def sign(self, artifact_path: str, credentials: SigningCredentials) -> SignResult:
        if not credentials.has_ios():
            return SignResult.skip(
                "iOS 凭证未配全 (需 ios_cert_path + ios_cert_password + ios_identity)"
            )

        # 1. security import 导入 .p12 证书到 keychain
        import_argv = [
            "security", "import", credentials.ios_cert_path,
            "-P", credentials.ios_cert_password,
            "-k", _KEYCHAIN,
            "-T", "/usr/bin/codesign",
        ]
        imp = await asyncio.to_thread(run_cmd, import_argv, 120, "security")
        if not imp.ok:
            return SignResult.fail(f"security import failed: {imp.stderr}")

        # 2. codesign 重签 (identity 来自 .p12 导入后的可用签名身份)
        codesign_argv = [
            "codesign", "--force",
            "--sign", credentials.ios_identity,
            artifact_path,
        ]
        cs = await asyncio.to_thread(run_cmd, codesign_argv, 600, "codesign")
        if not cs.ok:
            return SignResult.fail(f"codesign failed: {cs.stderr}")

        return SignResult(signed=True, signed_path=artifact_path)
