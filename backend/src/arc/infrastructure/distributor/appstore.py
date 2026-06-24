"""App Store Connect 上传器 — xcrun altool (v6.2.0 T2)。

上传链路:
1. 凭证未配 → DistributeResult.skip (graceful, 产物落制品仓可手动下载)
2. altool 要求 .p8 私钥文件 — 把 appstore_api_key 内容写到临时文件 AuthKey_{key_id}.p8
3. xcrun altool --upload-app --type ios --file {artifact} --apiKey {key_id}
   --apiIssuer {issuer_id} (用临时私钥文件)
4. 失败 → DistributeResult.fail

注意: 真实上传需 App Store Connect API key (.p8) + 网络。altool 在 macOS Xcode。
此处 mock subprocess 验证命令构造 + graceful skip。
未签名产物 (signed=False) 上传会被 App Store 拒绝, 此处仅 warning 不阻断 (调用方决定)。
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from arc.domain.deployment.distributor import (
    DistributeResult,
    DistributionCredentials,
    Distributor,
    DistributorType,
)
from arc.infrastructure.signer._cmd import run_cmd

logger = logging.getLogger(__name__)


class AppStoreDistributor(Distributor):
    """App Store Connect 上传 (xcrun altool)。"""

    distributor_type = DistributorType.APP_STORE

    async def upload(
        self, artifact_path: str, signed: bool, credentials: DistributionCredentials
    ) -> DistributeResult:
        if not credentials.has_app_store():
            return DistributeResult.skip(
                "App Store 凭证未配全 (需 appstore_issuer_id + key_id + api_key)"
            )

        if not signed:
            logger.warning("App Store 上传未签名产物, 商店可能拒绝")

        # altool 要求 .p8 私钥文件: 写临时文件 AuthKey_{key_id}.p8
        key_file = await asyncio.to_thread(
            self._write_key_file, credentials.appstore_key_id, credentials.appstore_api_key
        )
        try:
            argv = [
                "xcrun", "altool", "upload-app",
                "--type", "ios",
                "--file", artifact_path,
                "--apiKey", credentials.appstore_key_id,
                "--apiIssuer", credentials.appstore_issuer_id,
            ]
            result = await asyncio.to_thread(run_cmd, argv, 1800, "altool")
            if not result.ok:
                return DistributeResult.fail(f"altool failed: {result.stderr}")
            return DistributeResult(
                uploaded=True,
                store_url="",  # altool 不直接返回商店 URL, 需后续查 App Store Connect
            )
        finally:
            await asyncio.to_thread(os.remove, key_file)

    @staticmethod
    def _write_key_file(key_id: str, api_key: str) -> str:
        """写 .p8 私钥到临时文件 (altool 要求文件路径)。"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=f"AuthKey_{key_id}.p8", delete=False
        )
        tmp.write(api_key)
        tmp.close()
        return tmp.name
