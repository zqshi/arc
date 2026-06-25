"""DistributionService — 制品分发层编排 (v6.2.0 T5)。

职责 (artifact 显式建模后的 runtime 编排):
1. build_manifest: 扫描安装包产物 + 匹配签名状态 → DistributionManifest
2. distribute: 产物后缀 → 分发渠道, 调 distributor.upload (graceful skip 不阻断)
3. generate_*: 渲染下载页 HTML / manifest.json / Tauri latest.json / Sparkle appcast
4. publish: 四个渲染产物上传制品仓 (与产物同 prefix, 公开访问)
5. finalize: 编排上述全流程, 返回完整 manifest 供 DeployService 持久化

签名平台 (apple/windows/android) ≠ 分发渠道 (APP_STORE/PLAY_STORE/TAURI_UPDATER):
.app 走 APPLE 签名但走 TAURI_UPDATER 分发。build_manifest 按产物后缀映射签名平台查
sign_results; distribute 按产物后缀映射分发渠道调 distributor。
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from arc.domain.deployment.distribution import (
    ArtifactEntry,
    DistributionManifest,
    DistributionOutcome,
)
from arc.domain.deployment.distributor import DistributorType

logger = logging.getLogger(__name__)

# 可分发安装包后缀 (不含 .app 目录 — .app 是 codesign 签名对象, 本身不分发)
DISTRIBUTABLE_EXTS = (
    ".dmg", ".ipa", ".exe", ".msi", ".deb", ".AppImage", ".apk", ".aab",
)


class DistributionService:
    """制品分发层: 生成 + 编排 distributor 上传 + 渲染下载页/更新元数据。"""

    def __init__(self, storage=None):
        """storage 可注入 (测试用); 默认 publish 时 get_storage()。"""
        self._storage = storage

    # -- 构建 manifest --------------------------------------------------

    def build_manifest(
        self, deployment, version, sign_results, storage_prefix, local_dir
    ) -> DistributionManifest:
        """扫描安装包产物 + 匹配签名状态 → DistributionManifest。"""
        from arc.infrastructure.storage import get_public_url

        base = Path(local_dir)
        artifacts = []
        for ext in DISTRIBUTABLE_EXTS:
            for f in base.rglob(f"*{ext}"):
                if not f.is_file():
                    continue
                signer_type = self._signer_for_ext(ext)
                if signer_type is not None:
                    signed, signer_str, sig_id = self._sign_state_for(
                        sign_results, signer_type
                    )
                else:
                    signed, signer_str, sig_id = False, "", ""
                artifacts.append(
                    ArtifactEntry(
                        platform=self._platform_for(f.name),
                        filename=f.name,
                        download_url=get_public_url(f"{storage_prefix}/{f.name}"),
                        signed=signed,
                        signer_type=signer_str,
                        signature_id=sig_id,
                        size=f.stat().st_size,
                    )
                )
        pub_date = deployment.deployed_at.isoformat() if deployment.deployed_at else ""
        return DistributionManifest(
            version_name=version.name,
            version_id=str(version.id),
            changelog=version.changelog or "",
            pub_date=pub_date,
            artifacts=tuple(artifacts),
        )

    # -- distributor 编排 ------------------------------------------------

    async def distribute(
        self, local_dir, project, sign_results
    ) -> list[DistributionOutcome]:
        """产物后缀 → 渠道, 调 distributor.upload (每渠道取首个产物)。"""
        from arc.infrastructure.distributor import (
            get_distributor,
            load_distribution_creds_for_project,
        )

        base = Path(local_dir)
        channel_to_path: dict[DistributorType, str] = {}
        for ext in DISTRIBUTABLE_EXTS:
            for f in base.rglob(f"*{ext}"):
                if f.is_file():
                    channel_to_path.setdefault(self._channel_for_ext(ext), str(f))

        outcomes: list[DistributionOutcome] = []
        for channel, artifact_path in channel_to_path.items():
            dist = get_distributor(channel)
            if dist is None:
                outcomes.append(
                    DistributionOutcome(channel=channel, skipped=True, error="分发器未注册")
                )
                continue
            creds = load_distribution_creds_for_project(project, channel)
            signed = self._is_signed(artifact_path, sign_results)
            try:
                result = await dist.upload(artifact_path, signed=signed, credentials=creds)
            except Exception as e:  # distributor 异常不阻断 (graceful)
                logger.warning("distribute: %s 上传异常: %s", channel.value, e)
                outcomes.append(
                    DistributionOutcome(channel=channel, error=f"上传异常: {e}")
                )
                continue
            outcomes.append(
                DistributionOutcome(
                    channel=channel,
                    uploaded=result.uploaded,
                    skipped=result.skipped,
                    store_url=result.store_url,
                    error=result.error,
                )
            )
        return outcomes

    # -- 渲染 ------------------------------------------------------------

    def generate_download_page(self, manifest: DistributionManifest) -> str:
        """自包含 HTML 下载页 (产物表 + 签名状态 + 渠道状态 + 未签名 warning)。"""
        rows = []
        for a in manifest.artifacts:
            badge = "✓ signed" if a.signed else "⚠ unsigned"
            rows.append(
                f"<tr><td>{a.platform}</td><td>{a.filename}</td><td>{badge}</td>"
                f'<td><a href="{a.download_url}">download</a></td></tr>'
            )
        warning = (
            '<p class="warn">⚠ 含未签名产物, 谨慎下载</p>'
            if manifest.has_unsigned()
            else ""
        )
        dist_items = "".join(
            f"<li>{o.channel.value}: "
            f"{'uploaded' if o.uploaded else 'skipped' if o.skipped else 'failed'}"
            f"{f' → {o.store_url}' if o.store_url else ''}</li>"
            for o in manifest.distributions
        )
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{manifest.version_name}</title></head><body>"
            f"<h1>{manifest.version_name}</h1><p>{manifest.changelog}</p>{warning}"
            "<table><tr><th>Platform</th><th>File</th><th>Sign</th><th>Link</th></tr>"
            f"{''.join(rows)}</table><ul>{dist_items}</ul></body></html>"
        )

    def generate_manifest_json(self, manifest: DistributionManifest) -> str:
        """结构化清单 JSON (Arc API 源 + 制品仓存档)。"""
        return json.dumps(
            dataclasses.asdict(manifest),
            ensure_ascii=False,
            indent=2,
            default=lambda o: o.value if isinstance(o, DistributorType) else str(o),
        )

    def generate_latest_json(self, manifest: DistributionManifest) -> str:
        """Tauri updater v2 latest.json (version/notes/pub_date/platforms)。"""
        platforms = {}
        for a in manifest.artifacts:
            platforms[a.platform] = {
                "url": a.download_url,
                "signature": a.signature_id or "",
            }
        return json.dumps(
            {
                "version": manifest.version_name,
                "notes": manifest.changelog,
                "pub_date": manifest.pub_date,
                "platforms": platforms,
            },
            ensure_ascii=False,
            indent=2,
        )

    def generate_appcast(self, manifest: DistributionManifest) -> str:
        """Sparkle appcast RSS XML (仅 macOS 产物, edSignature 用 signature_id 占位)。"""
        items = []
        for a in manifest.artifacts:
            if "darwin" not in a.platform:
                continue
            items.append(
                f"<item><title>{manifest.version_name}</title>"
                f"<sparkle:version>{manifest.version_name}</sparkle:version>"
                f'<enclosure url="{a.download_url}" sparkle:edSignature="{a.signature_id}" '
                f'length="{a.size}" type="application/octet-stream"/></item>'
            )
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<rss version="2.0" '
            'xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<channel><title>{manifest.version_name}</title>'
            f"{''.join(items)}</channel></rss>"
        )

    async def publish(
        self, manifest: DistributionManifest, storage_prefix: str
    ) -> dict[str, str]:
        """四个渲染产物上传制品仓 (与产物同 prefix), 返回 {filename: url}。"""
        storage = self._storage
        if storage is None:
            from arc.infrastructure.storage import get_storage
            storage = get_storage()
        files = {
            "download.html": (self.generate_download_page(manifest), "text/html"),
            "manifest.json": (self.generate_manifest_json(manifest), "application/json"),
            "latest.json": (self.generate_latest_json(manifest), "application/json"),
            "appcast.xml": (self.generate_appcast(manifest), "application/xml"),
        }
        urls: dict[str, str] = {}
        for name, (content, ctype) in files.items():
            url = await storage.async_upload(
                f"{storage_prefix}/{name}", content.encode(), ctype
            )
            urls[name] = url
        return urls

    async def finalize(
        self, deployment, version, project, local_dir, sign_results, storage_prefix
    ) -> DistributionManifest:
        """编排全流程: build → distribute → publish, 返回完整 manifest。"""
        manifest = self.build_manifest(
            deployment, version, sign_results, storage_prefix, local_dir
        )
        outcomes = await self.distribute(local_dir, project, sign_results)
        manifest = dataclasses.replace(manifest, distributions=tuple(outcomes))
        urls = await self.publish(manifest, storage_prefix)
        return dataclasses.replace(
            manifest, download_page_url=urls.get("download.html", "")
        )

    # -- 后缀 → 平台/渠道/签名器 映射 -----------------------------------

    @staticmethod
    def _platform_for(filename: str) -> str:
        name = filename.lower()
        if name.endswith(".apk") or name.endswith(".aab"):
            return "android-universal"
        arch = "aarch64" if ("aarch64" in name or "arm64" in name) else "x86_64"
        if name.endswith(".dmg") or name.endswith(".ipa"):
            return f"darwin-{arch}"
        if name.endswith(".exe") or name.endswith(".msi"):
            return f"windows-{arch}"
        if name.endswith(".deb") or name.endswith(".appimage"):
            return f"linux-{arch}"
        return "unknown"

    @staticmethod
    def _signer_for_ext(ext: str):
        """产物后缀 → 签名平台 (None = 该后缀无签名, 如 .deb/.AppImage)。"""
        from arc.domain.deployment.signer import SignerType

        return {
            ".dmg": SignerType.APPLE, ".ipa": SignerType.APPLE,
            ".exe": SignerType.WINDOWS, ".msi": SignerType.WINDOWS,
            ".apk": SignerType.ANDROID, ".aab": SignerType.ANDROID,
        }.get(ext)

    @staticmethod
    def _channel_for_ext(ext: str) -> DistributorType:
        """产物后缀 → 分发渠道 (默认 TAURI_UPDATER 桌面自更新)。"""
        if ext in (".apk", ".aab"):
            return DistributorType.PLAY_STORE
        if ext == ".ipa":
            return DistributorType.APP_STORE
        return DistributorType.TAURI_UPDATER

    @staticmethod
    def _sign_state_for(sign_results, signer_type) -> tuple[bool, str, str]:
        """从 sign_results 取某平台签名状态 (任一成功则 signed)。
        返回 (signed, signer_str, sig_id)。"""
        for st, _path, result in sign_results:
            if st == signer_type and result.signed:
                return True, st.value, result.signature_id
        for st, _path, result in sign_results:
            if st == signer_type:
                return False, st.value, ""
        return False, "", ""

    @classmethod
    def _is_signed(cls, path: str, sign_results) -> bool:
        ext = Path(path).suffix.lower()
        signer_type = cls._signer_for_ext(ext)
        if signer_type is None:
            return False
        signed, _, _ = cls._sign_state_for(sign_results, signer_type)
        return signed
