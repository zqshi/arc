"""分发器抽象层 — 把签名后产物上传到商店/分发渠道的领域契约 (v6.2.0 T1)。

分发是领域行为 ("把产物上架到商店/更新渠道"), 具体实现 (App Store Connect /
Play Console / Tauri updater) 在 infrastructure/distributor/。与 v6.1 Signer
同构 (domain 定义契约, infrastructure 实现)。

graceful skip 原则 (与签名一致):
- 分发凭证未配 → DistributeResult.skip(), 产物落制品仓可手动下载
- 上传失败 → DistributeResult.fail(), 不阻断 (产物已在制品仓)
- 上传成功 → DistributeResult(uploaded=True, store_url=...)

凭证项目维度加密存储 (复用 v6.1 crypto 基础设施), 与签名凭证分离:
- SigningCredentials (v6.1): 签名用 (Apple/Win/Android keystore)
- DistributionCredentials (本版本): 分发用 (AppStore API/Play JSON/Tauri updater)
play_key_json 从 v6.1 SigningCredentials 归位到本类 (它本就是分发凭证)。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import StrEnum


class DistributorType(StrEnum):
    """分发渠道 — 决定上传到哪个商店/更新服务。"""

    APP_STORE = "app_store"  # App Store Connect (iOS/macOS)
    PLAY_STORE = "play_store"  # Google Play Console (Android)
    TAURI_UPDATER = "tauri_updater"  # Tauri updater 自建更新服务


@dataclass(frozen=True)
class DistributionCredentials:
    """分发凭证值对象 — 聚合三渠道凭证, 全 optional (空=graceful skip)。

    从 config 加载为空, 从项目解密加载 (复用 v6.1 crypto + Project 加密字段)。
    """

    # App Store Connect (App Store Connect API key)
    appstore_issuer_id: str = ""  # Issuer ID (UUID)
    appstore_key_id: str = ""  # Key ID
    appstore_api_key: str = ""  # API key (.p8 内容, 非文件路径)

    # Google Play Console (service account JSON, v6.1 归位)
    play_key_json: str = ""
    play_package_name: str = ""  # 应用包名 (applicationId), Play edit API 必需

    # Tauri updater (自建更新服务)
    tauri_updater_url: str = ""  # 更新服务器 URL
    tauri_updater_secret: str = ""  # 更新签名密钥

    def is_empty(self) -> bool:
        return not (
            self.has_app_store() or self.has_play_store() or self.has_tauri_updater()
        )

    def has_app_store(self) -> bool:
        return bool(self.appstore_issuer_id and self.appstore_key_id and self.appstore_api_key)

    def has_play_store(self) -> bool:
        # service account JSON + 应用包名齐备才算配全 (edit API 两都需要)
        return bool(self.play_key_json and self.play_package_name)

    def has_tauri_updater(self) -> bool:
        return bool(self.tauri_updater_url and self.tauri_updater_secret)


@dataclass(frozen=True)
class DistributeResult:
    """分发结果值对象。

    三态: uploaded=True (成功, 含 store_url) / skipped=True (凭证未配, 产物落制品仓) /
    两者皆 False (失败)。
    """

    uploaded: bool = False
    skipped: bool = False
    store_url: str = ""  # 商店/渠道公开地址 (成功时)
    error: str = ""  # skip 原因 / 失败信息

    @staticmethod
    def skip(reason: str) -> "DistributeResult":
        """graceful skip — 凭证未配, 产物落制品仓可手动下载。"""
        return DistributeResult(skipped=True, error=reason)

    @staticmethod
    def fail(error: str) -> "DistributeResult":
        """分发失败 — uploaded=False, skipped=False。"""
        return DistributeResult(uploaded=False, error=error)


class Distributor(abc.ABC):
    """分发器抽象基类 — 把签名后产物上传到商店/分发渠道。

    每种渠道 (App Store / Play / Tauri updater) 对应一个 Distributor 实现。
    新增渠道时:
    1. 在 infrastructure/distributor/ 下新建 ``XxxDistributor(Distributor)``
    2. 在 ``get_distributor()`` 工厂注册 (DistributorType → Distributor 映射)

    职责: 只上传分发, 不构建不签名 (构建 v6.0, 签名 v6.1)。
    凭证未配 → 返回 skipped, 不抛异常。
    """

    distributor_type: DistributorType  # 子类声明所属渠道

    @abc.abstractmethod
    async def upload(
        self,
        artifact_path: str,
        signed: bool,
        credentials: DistributionCredentials,
    ) -> DistributeResult:
        """上传签名后产物到商店/渠道。

        Args:
            artifact_path: 构建产物路径 (已签名, 见 signed)
            signed: 产物是否已签名 (v6.1 Signer 结果); 部分渠道要求签名才接受
            credentials: 分发凭证 (未配该渠道 → 返回 skipped)

        Returns:
            DistributeResult — uploaded/skipped/failure 三态
        """
        raise NotImplementedError
