"""鸿蒙签名器 — hap-sign-tool sign-app (v6.19 T10)。

签名链路:
1. 凭证未配 → SignResult.skip (graceful, 不阻断构建)
2. hap-sign-tool sign-app -keyAlias {alias} -appCertFile {cer} -profileFile {p7b}
   -inFile {hap} -outFile {out} -keystoreFile {p12} -keystorePwd {pwd} -keyPwd {kpwd}
3. 失败 → SignResult.fail; 成功 → SignResult(signed=True)

注意: hap-sign-tool 是华为 DevEco 工具, 非 macOS/Linux 原生。真实签名需鸿蒙 runner
+ .p12 keystore + .cer 证书 + .p7b profile。此处 mock subprocess 验证命令构造
+ graceful skip, 与 WindowsSigner 同构 (v6.1 mock 先行模式)。
"""
from __future__ import annotations

import asyncio
import logging

from arc.domain.deployment.signer import Signer, SignerType, SigningCredentials, SignResult
from arc.infrastructure.signer._cmd import run_cmd

logger = logging.getLogger(__name__)


class HarmonySigner(Signer):
    """鸿蒙 .hap 签名 (hap-sign-tool sign-app)。"""

    signer_type = SignerType.HARMONY

    async def sign(self, artifact_path: str, credentials: SigningCredentials) -> SignResult:
        if not credentials.has_harmony():
            return SignResult.skip(
                "鸿蒙凭证未配全 (需 harmony_keystore_path + harmony_keystore_password "
                "+ harmony_key_alias + harmony_cert_path + harmony_profile_path)"
            )

        # key_password 可与 keystore_password 相同, 缺失时用 keystore_password 兜底
        key_pwd = credentials.harmony_key_password or credentials.harmony_keystore_password
        argv = [
            "hap-sign-tool", "sign-app",
            "-keyAlias", credentials.harmony_key_alias,
            "-signAlg", "SHA256withRSA",
            "-mode", "localSign",
            "-appCertFile", credentials.harmony_cert_path,
            "-profileFile", credentials.harmony_profile_path,
            "-inFile", artifact_path,
            "-outFile", artifact_path,  # 原地签名 (真实场景 outFile 可同路径或 .signed.hap)
            "-keystoreFile", credentials.harmony_keystore_path,
            "-keystorePwd", credentials.harmony_keystore_password,
            "-keyPwd", key_pwd,
        ]
        result = await asyncio.to_thread(run_cmd, argv, 300, "hap-sign-tool")
        if not result.ok:
            return SignResult.fail(f"hap-sign-tool failed: {result.stderr}")
        return SignResult(signed=True, signed_path=artifact_path)
