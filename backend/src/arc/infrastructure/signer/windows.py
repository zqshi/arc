"""Windows 签名器 — signtool (v6.1.0 T3)。

签名链路:
1. 凭证未配 → SignResult.skip (graceful)
2. signtool sign /f {cert_path} /p {password} /tr {timestamp} /td sha256 {artifact}
3. 失败 → SignResult.fail

注意: signtool 是 Windows SDK 工具, 非 macOS/Linux 原生。真实签名需 Windows runner
或 wine + signtool。此处 mock subprocess 验证命令构造 + graceful skip。
EV (Extended Validation) 证书需 /csp /k 参数指定私钥容器, 本版简化为文件证书。
"""
from __future__ import annotations

import asyncio
import logging

from arc.domain.deployment.signer import Signer, SignerType, SigningCredentials, SignResult
from arc.infrastructure.signer._cmd import run_cmd

logger = logging.getLogger(__name__)

# RFC3161 时间戳服务器 (DigiCert, signtool /tr)
_TIMESTAMP_URL = "http://timestamp.digicert.com"


class WindowsSigner(Signer):
    """Windows EV 证书签名 (signtool)。"""

    signer_type = SignerType.WINDOWS

    async def sign(self, artifact_path: str, credentials: SigningCredentials) -> SignResult:
        if not credentials.has_windows():
            return SignResult.skip(
                "Windows 凭证未配全 (需 win_ev_cert_path + win_ev_password)"
            )

        argv = [
            "signtool", "sign",
            "/f", credentials.win_ev_cert_path,
            "/p", credentials.win_ev_password,
            "/tr", _TIMESTAMP_URL,
            "/td", "sha256",
            artifact_path,
        ]
        result = await asyncio.to_thread(run_cmd, argv, 300, "signtool")
        if not result.ok:
            return SignResult.fail(f"signtool failed: {result.stderr}")
        return SignResult(signed=True, signed_path=artifact_path)
