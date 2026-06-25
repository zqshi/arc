"""Google Play Console 上传器 — Play Developer API v3 (v6.2.0 T3)。

与 T4 (Tauri updater) 同构 (HTTP API, httpx), 与 T2 (App Store, altool CLI) 不同。
Play 无 CLI 工具, 必须走 REST API。

上传链路:
1. 凭证未配 (play_key_json 或 play_package_name 缺) → skip (graceful)
2. 解析 service account JSON → private_key/client_email/token_uri
3. RS256 JWT 签名 (jose, 复用 v6.1 已有依赖, 不引入 PyJWT) → OAuth2 access_token
4. create edit → upload AAB (uploadType=media) → commit edit
5. 失败 → fail; 成功 → uploaded (store_url 留空, commit 后在 Play Console 查看)

非阻塞理念 (与签名/其他分发器一致):
- commit 后 AAB 处于 draft, 发布到 track 由人在 Console 手动决定
  (自动化只到"上传到商店草稿", 不自动上线 — 避免误发布)
- store_url 留空 (Play Console 应用页含 developer account id, 无法稳定构造),
  与 T2 appstore (altool 不返回 URL) 一致
"""
from __future__ import annotations

import json
import logging
import time

import httpx
from jose import jwt

from arc.domain.deployment.distributor import (
    DistributeResult,
    DistributionCredentials,
    Distributor,
    DistributorType,
)

logger = logging.getLogger(__name__)

_PLAY_API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
_PLAY_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
_OAUTH_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"


class _PlayError(Exception):
    """Play 上传链路错误 (已含可读信息, upload 捕获转 fail, 不阻断)。"""


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class PlayStoreDistributor(Distributor):
    """Google Play Console 上传 (Play Developer API v3, httpx + jose RS256)。"""

    distributor_type = DistributorType.PLAY_STORE

    async def upload(
        self, artifact_path: str, signed: bool, credentials: DistributionCredentials
    ) -> DistributeResult:
        if not credentials.has_play_store():
            return DistributeResult.skip(
                "Play Console 凭证未配全 (需 play_key_json + play_package_name)"
            )

        if not signed:
            logger.warning("Play Console 上传未签名产物, 商店可能拒绝")

        try:
            sa = json.loads(credentials.play_key_json)
        except (json.JSONDecodeError, ValueError, TypeError):
            return DistributeResult.fail("play_key_json 不是合法 service account JSON")

        if not (
            isinstance(sa, dict)
            and sa.get("private_key")
            and sa.get("client_email")
            and sa.get("token_uri")
        ):
            return DistributeResult.fail(
                "play_key_json 缺少 private_key/client_email/token_uri"
            )

        package = credentials.play_package_name
        try:
            async with httpx.AsyncClient(timeout=1800.0) as client:
                access_token = await self._auth(client, sa)
                edit_id = await self._create_edit(client, access_token, package)
                await self._upload_aab(
                    client, access_token, package, edit_id, artifact_path
                )
                await self._commit_edit(client, access_token, package, edit_id)
        except _PlayError as e:
            return DistributeResult.fail(str(e))
        except httpx.HTTPError as e:
            return DistributeResult.fail(f"Play 上传网络错误: {e}")

        return DistributeResult(uploaded=True, store_url="")

    async def _auth(self, client: httpx.AsyncClient, sa: dict) -> str:
        """RS256 JWT → OAuth2 access_token (service account flow)。"""
        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": _PLAY_SCOPE,
            "aud": sa["token_uri"],
            "iat": now,
            "exp": now + 3600,
        }
        try:
            assertion = jwt.encode(
                payload,
                sa["private_key"],
                algorithm="RS256",
                headers={"kid": sa.get("private_key_id")},
            )
        except Exception as e:  # jose 签名失败 (私钥格式错等)
            raise _PlayError(f"JWT 签名失败: {e}") from e

        resp = await client.post(
            sa["token_uri"],
            data={"grant_type": _OAUTH_GRANT, "assertion": assertion},
        )
        if resp.status_code != 200:
            raise _PlayError(f"token HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["access_token"]
        except (KeyError, ValueError) as e:
            raise _PlayError(f"token 响应解析失败: {e}") from e

    async def _create_edit(
        self, client: httpx.AsyncClient, token: str, package: str
    ) -> str:
        url = f"{_PLAY_API}/{package}/edits"
        resp = await client.post(url, headers=_bearer(token), json={})
        if resp.status_code not in (200, 201):
            raise _PlayError(f"create edit HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["id"]
        except (KeyError, ValueError) as e:
            raise _PlayError(f"create edit 响应解析失败: {e}") from e

    async def _upload_aab(
        self,
        client: httpx.AsyncClient,
        token: str,
        package: str,
        edit_id: str,
        artifact_path: str,
    ) -> None:
        url = f"{_PLAY_API}/{package}/edits/{edit_id}/aab?uploadType=media"
        with open(artifact_path, "rb") as f:
            resp = await client.post(
                url,
                headers={**_bearer(token), "Content-Type": "application/octet-stream"},
                content=f,
            )
        if resp.status_code not in (200, 201):
            raise _PlayError(f"upload aab HTTP {resp.status_code}: {resp.text[:200]}")

    async def _commit_edit(
        self, client: httpx.AsyncClient, token: str, package: str, edit_id: str
    ) -> None:
        url = f"{_PLAY_API}/{package}/edits/{edit_id}:commit"
        resp = await client.post(url, headers=_bearer(token))
        if resp.status_code not in (200, 201):
            raise _PlayError(f"commit HTTP {resp.status_code}: {resp.text[:200]}")
