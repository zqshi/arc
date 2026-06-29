"""签名器抽象层 — 对构建产物加签的领域契约 (v6.1.0 T1)。

签名是领域行为 ("对产物签名使其可被信任"), 具体实现 (codesign/signtool/apksigner)
在 infrastructure/signer/。本模块定义接口 + 值对象, 与 domain 的 repository
接口同构 (domain 定义契约, infrastructure 实现)。

graceful skip 原则 (核心设计):
- 凭证未配 → SignResult.skipped() 返回, signed=False, 构建不阻断 (仅 warning)
- 凭证已配但签名失败 → SignResult.failure(), signed=False (是否阻断由调用方决定)
- 凭证已配且签名成功 → SignResult(signed=True)

凭证可配置非阻塞: v6.1 不要求用户必须配齐 Apple/Win/Play 凭证才能构建。
未配 → 产物以未签名状态落制品目录 (分发层 v6.2 决定是否接受未签名产物)。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import StrEnum


class SignerType(StrEnum):
    """签名平台 — 决定用哪个签名工具。"""

    APPLE = "apple"  # codesign + xcrun notarytool (macOS 原生)
    WINDOWS = "windows"  # signtool (EV 证书)
    ANDROID = "android"  # apksigner (JDK + keystore)
    IOS = "ios"  # security import + codesign (v6.19 T7, .ipa + provisioning profile)
    HARMONY = "harmony"  # hap-sign-tool sign-app (v6.19 T10, .p12 + .cer + .p7b profile)


@dataclass(frozen=True)
class SigningCredentials:
    """签名凭证值对象 — 聚合三平台凭证, 全 optional (空=graceful skip)。

    从 config.Settings 加载。任一平台凭证缺失 → 该平台签名 skipped, 不阻断。
    """

    # Apple Developer
    apple_id: str = ""  # Apple ID (邮箱, notarytool --apple-id 提交用, v6.13 P3 修正)
    apple_dev_id: str = ""  # Developer ID Application 证书 identity (codesign --sign)
    apple_team_id: str = ""  # Apple Team ID (notarytool --team-id)
    apple_app_password: str = ""  # App-specific password (notarytool --password)

    # Windows EV 证书
    win_ev_cert_path: str = ""  # .pfx 证书文件路径
    win_ev_password: str = ""  # 证书密码

    # Android 签名 (app signing keystore, .jks — apksigner 用)
    android_keystore_path: str = ""  # release keystore 文件路径
    android_keystore_password: str = ""  # keystore 密码
    android_key_alias: str = ""  # 签名 key 别名
    android_key_password: str = ""  # key 密码 (可与 keystore 密码不同)
    # 注: Play 上传密钥 (play_key_json) 是分发凭证, v6.2 归位到 DistributionCredentials

    # iOS 签名 (v6.19 T7 — security import + codesign, .ipa 重签)
    ios_cert_path: str = ""  # .p12 证书文件路径 (security import)
    ios_cert_password: str = ""  # .p12 密码
    ios_identity: str = ""  # 签名 identity (codesign --sign, 如 "iPhone Distribution: Team")
    ios_provisioning_profile: str = ""  # .mobileprovision 文件路径 (分发嵌入用, has 判定不强制)

    # 鸿蒙签名 (v6.19 T10 — hap-sign-tool sign-app, .hap)
    harmony_keystore_path: str = ""  # .p12 keystore 文件路径
    harmony_keystore_password: str = ""  # keystore 密码
    harmony_key_alias: str = ""  # 签名 key 别名
    harmony_key_password: str = ""  # key 密码 (可与 keystore 密码相同, 缺失则用 keystore 密码)
    harmony_cert_path: str = ""  # .cer 证书文件路径 (appCertFile)
    harmony_profile_path: str = ""  # .p7b profile 文件路径 (profileFile)

    def is_empty(self) -> bool:
        """全平台凭证均未配置。"""
        return not (
            self.has_apple()
            or self.has_windows()
            or self.has_android()
            or self.has_ios()
            or self.has_harmony()
        )

    def has_apple(self) -> bool:
        """Apple 签名+公证完整凭证 (apple_id + identity + team + app password)。

        apple_id (邮箱) 与 team_id 是不同概念: notarytool --apple-id 需 Apple ID 邮箱,
        --team-id 需 Team ID (v6.13 P3 修正: v6.1 误用 team_id 兼作 apple_id)。
        """
        return bool(
            self.apple_id
            and self.apple_dev_id
            and self.apple_team_id
            and self.apple_app_password
        )

    def has_windows(self) -> bool:
        return bool(self.win_ev_cert_path and self.win_ev_password)

    def has_android(self) -> bool:
        """Android 签名凭证 (app signing keystore, 非 Play 上传密钥)。"""
        return bool(
            self.android_keystore_path
            and self.android_keystore_password
            and self.android_key_alias
        )

    def has_ios(self) -> bool:
        """iOS 签名凭证 (.p12 + identity, security import + codesign 用)。

        证书路径 + 密码 + identity 三者齐 → 可签名 (与 has_windows 同构)。
        provisioning_profile 缺失时 codesign 仍可执行 (仅无法分发到设备),
        故不纳入 has 判定, 避免过度 skip (分发关注归 DistributionCredentials)。
        """
        return bool(
            self.ios_cert_path
            and self.ios_cert_password
            and self.ios_identity
        )

    def has_harmony(self) -> bool:
        """鸿蒙签名凭证 (.p12 keystore + alias + .cer + .p7b profile)。

        hap-sign-tool sign-app 必需: keystore + 密码 + alias + appCertFile + profileFile。
        key_password 可与 keystore_password 相同, 缺失时签名器用 keystore_password 兜底,
        故不纳入 has 判定 (缺失触发 skip 会阻断可用配置)。
        """
        return bool(
            self.harmony_keystore_path
            and self.harmony_keystore_password
            and self.harmony_key_alias
            and self.harmony_cert_path
            and self.harmony_profile_path
        )


@dataclass(frozen=True)
class SignResult:
    """签名结果值对象。

    三态: signed=True (成功) / skipped=True (凭证未配, 不阻断) / 两者皆 False (失败)。
    """

    signed: bool = False
    skipped: bool = False
    signature_id: str = ""  # 签名标识 (如 notarize ticket id)
    signed_path: str = ""  # 签名后产物路径 (通常同 artifact_path, 签名就地)
    error: str = ""  # skip 原因 / 失败信息

    @staticmethod
    def skip(reason: str) -> "SignResult":
        """graceful skip — 凭证未配, 构建不阻断。"""
        return SignResult(skipped=True, error=reason)

    @staticmethod
    def fail(error: str) -> "SignResult":
        """签名失败 — signed=False, skipped=False (是否阻断由调用方决定)。"""
        return SignResult(signed=False, error=error)


class Signer(abc.ABC):
    """签名器抽象基类 — 对构建产物加签。

    每种平台 (Apple/Windows/Android) 对应一个 Signer 实现。新增平台时:
    1. 在 infrastructure/signer/ 下新建 ``XxxSigner(Signer)``
    2. 在 ``get_signer()`` 工厂注册 (build_target → Signer 映射)

    职责: 只签名, 不分发 (分发在 v6.2)。凭证未配 → 返回 skipped, 不抛异常。
    """

    signer_type: SignerType  # 子类声明所属平台

    @abc.abstractmethod
    async def sign(
        self,
        artifact_path: str,
        credentials: SigningCredentials,
    ) -> SignResult:
        """对产物加签。

        Args:
            artifact_path: 构建产物路径 (如 .deb / .exe / .apk)
            credentials: 签名凭证 (未配该平台 → 返回 skipped)

        Returns:
            SignResult — signed/skipped/failure 三态
        """
        raise NotImplementedError
