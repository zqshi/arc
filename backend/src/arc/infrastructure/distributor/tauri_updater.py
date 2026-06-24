"""Tauri updater 上传器 — 自建更新服务 (v6.2.0 T4)。

上传链路:
1. 凭证未配 → DistributeResult.skip (graceful, 产物落制品仓可手动下载)
2. httpx PUT {updater_url}/{filename} (Authorization: Bearer {secret}, body=产物字节)
3. 服务器返回 2xx → uploaded=True, store_url=产物在更新服务的 URL
4. 非 2xx → DistributeResult.fail

与 T2 (AppStore, altool CLI) 不同: Tauri updater 用 HTTP API (httpx), 无 CLI 工具。
更新元数据 (latest.json) 在 T5 制品分发层生成, 本上传器只传产物文件。
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from arc.domain.deployment.distributor import (
    DistributeResult,
    DistributionCredentials,
    Distributor,
    DistributorType,
)

logger = logging.getLogger(__name__)


class TauriUpdaterDistributor(Distributor):
    """Tauri 自建更新服务上传 (httpx PUT)。"""

    distributor_type = DistributorType.TAURI_UPDATER

    async def upload(
        self, artifact_path: str, signed: bool, credentials: DistributionCredentials
    ) -> DistributeResult:
        if not credentials.has_tauri_updater():
            return DistributeResult.skip(
                "Tauri updater 凭证未配全 (需 tauri_updater_url + tauri_updater_secret)"
            )

        if not signed:
            logger.warning("Tauri updater 上传未签名产物, 客户端更新可能拒绝")

        filename = Path(artifact_path).name
        upload_url = f"{credentials.tauri_updater_url.rstrip('/')}/{filename}"

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                with open(artifact_path, "rb") as f:
                    resp = await client.put(
                        upload_url,
                        content=f,
                        headers={"Authorization": f"Bearer {credentials.tauri_updater_secret}"},
                    )
        except httpx.HTTPError as e:
            return DistributeResult.fail(f"tauri updater 上传失败: {e}")

        if not (200 <= resp.status_code < 300):
            return DistributeResult.fail(
                f"tauri updater 上传失败 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        return DistributeResult(uploaded=True, store_url=upload_url)
