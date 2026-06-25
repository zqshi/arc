"""制品分发清单值对象 — 一个版本的分发产物 + 渠道结果的结构化建模 (v6.2.0 T5)。

artifact 显式建模 (符合"先 artifact 后 runtime"原则): 把"签名后产物分发到商店/更新
渠道"的结果显式建模为值对象, 供下载页 / 更新元数据 / Arc API 消费。与 SignResult
(v6.1) / DistributeResult (T1) 同构: 领域行为的结果用值对象承载, 不裸 dict。

数据来源:
- 签名状态: _sign_artifact 汇总 sign_results, build_manifest 按产物路径匹配得 signed
- distributor 结果: DistributionOutcome 包装 DistributeResult + 渠道

签名平台 (apple/windows/android) 与分发渠道 (APP_STORE/PLAY_STORE/TAURI_UPDATER)
是两个维度 — .app 走 APPLE 签名但走 TAURI_UPDATER 分发。
"""
from __future__ import annotations

from dataclasses import dataclass

from arc.domain.deployment.distributor import DistributorType


@dataclass(frozen=True)
class ArtifactEntry:
    """单个分发产物 (安装包)。

    分发对象是打包好的安装包 (.dmg/.exe/.msi/.deb/.AppImage/.apk/.aab/.ipa),
    非 .app 目录 (.app 是 codesign 签名对象, 本身不分发)。
    """

    platform: str  # darwin-aarch64 / linux-x86_64 / windows-x86_64 / android-universal
    filename: str
    download_url: str
    signed: bool = False
    signer_type: str = ""  # apple/windows/android (签名平台, 与分发渠道不同维度)
    signature_id: str = ""  # 签名标识 (notarize ticket id 等); minisign .sig 待后续
    size: int = 0

    @property
    def is_unsigned(self) -> bool:
        """未签名产物 (下载页需标 warning)。"""
        return not self.signed


@dataclass(frozen=True)
class DistributionOutcome:
    """单渠道分发结果 (包装 DistributeResult + 渠道)。

    三态: uploaded=True (成功, 含 store_url) / skipped=True (凭证未配) /
    两者皆 False (失败)。与 DistributeResult 三态对齐。
    """

    channel: DistributorType
    uploaded: bool = False
    skipped: bool = False
    store_url: str = ""
    error: str = ""


@dataclass(frozen=True)
class DistributionManifest:
    """一个版本/部署的完整分发清单。

    聚合产物列表 + 各渠道分发结果 + 版本元数据, 是下载页/更新元数据/Arc API 的
    统一数据源。DB 持久化为 JSON (distribution_manifest 字段), 制品仓渲染为
    download.html / manifest.json / latest.json / appcast。
    """

    version_name: str
    version_id: str
    changelog: str = ""
    pub_date: str = ""  # ISO8601 (如 2026-06-25T12:00:00Z)
    artifacts: tuple[ArtifactEntry, ...] = ()
    distributions: tuple[DistributionOutcome, ...] = ()
    download_page_url: str = ""

    def has_unsigned(self) -> bool:
        """是否存在未签名产物 (决定下载页是否显示 warning)。"""
        return any(a.is_unsigned for a in self.artifacts)

    def channel_outcome(self, channel: DistributorType) -> DistributionOutcome | None:
        """取某渠道的分发结果 (未分发返回 None)。"""
        for o in self.distributions:
            if o.channel == channel:
                return o
        return None
