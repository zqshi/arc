"""Tests for domain/artifact BuildArtifactKind 簇 — 构建产物物理形态 + 签名链路。

对应 domain/artifact/value_objects.py 的 BuildArtifactKind / KIND_SIGNER_TYPE /
TARGET_ARTIFACT_KINDS (v6.19 T2)。独立成文件因系 v6.19 新增概念簇, 且需跨真相源
测 execution_backend 一致性 (BuildTarget 双登记不变量)。

domain 层零 mock: 直接查表/构造, 验证映射 + 全登记不变量 + 跨真相源一致性。
"""

import pytest

from arc.domain.artifact.value_objects import (
    EXTENSION_KIND,
    KIND_SIGNER_TYPE,
    TARGET_ARTIFACT_KINDS,
    BuildArtifactKind,
    signer_for_kind,
    target_artifact_kinds,
)
from arc.domain.deployment.signer import SignerType
from arc.domain.sandbox.execution_backend import (
    TARGET_BACKENDS,
    target_execution_backend,
)
from arc.domain.sandbox.value_objects import BuildTarget


class TestBuildArtifactKind:
    def test_enum_values_are_stable_strings(self):
        """枚举值是稳定字符串 (供 BUILD artifact content / 日志契约引用)。"""
        assert BuildArtifactKind.DEB.value == "deb"
        assert BuildArtifactKind.APPIMAGE.value == "appimage"
        assert BuildArtifactKind.WEB_DIST.value == "web_dist"
        assert BuildArtifactKind.APK.value == "apk"

    def test_windows_kinds_defined(self):
        """v6.19 T2: Windows 产物形态 .msi/.exe 已建模。"""
        assert BuildArtifactKind.MSI.value == "msi"
        assert BuildArtifactKind.EXE.value == "exe"


class TestKindSignerType:
    def test_all_kinds_registered(self):
        """全登记不变量: 每个 BuildArtifactKind 都在 KIND_SIGNER_TYPE 显式决策签名平台。

        漏登记会导致 signer_for_kind 抛 KeyError。强制新形态 (如 T5 IPA) 同步登记
        签名决策, 防止静默不签。
        """
        for kind in BuildArtifactKind:
            assert kind in KIND_SIGNER_TYPE, (
                f"{kind} 未登记签名平台 — 新增 BuildArtifactKind 必须在 "
                f"KIND_SIGNER_TYPE 显式决策 (SignerType 或 None 不签)"
            )

    def test_windows_kinds_route_to_windows_signer(self):
        """v6.19 T2: .msi/.exe → SignerType.WINDOWS (复用 v6.1 signtool, 签名链路声明)。"""
        assert KIND_SIGNER_TYPE[BuildArtifactKind.MSI] is SignerType.WINDOWS
        assert KIND_SIGNER_TYPE[BuildArtifactKind.EXE] is SignerType.WINDOWS

    def test_apk_routes_to_android(self):
        assert KIND_SIGNER_TYPE[BuildArtifactKind.APK] is SignerType.ANDROID

    def test_ipa_hap_route_to_ios_harmony(self):
        """v6.19 T7/T10 done: .ipa→IOS, .hap→HARMONY (KIND_SIGNER_TYPE 已回填, 取代 T5/T8 占位 None)。"""
        assert KIND_SIGNER_TYPE[BuildArtifactKind.IPA] is SignerType.IOS
        assert KIND_SIGNER_TYPE[BuildArtifactKind.HAP] is SignerType.HARMONY

    def test_linux_and_web_kinds_unsigned(self):
        """Linux (.deb/AppImage) / web (dist) 无标准代码签名机制 → None 不签。"""
        assert KIND_SIGNER_TYPE[BuildArtifactKind.DEB] is None
        assert KIND_SIGNER_TYPE[BuildArtifactKind.APPIMAGE] is None
        assert KIND_SIGNER_TYPE[BuildArtifactKind.WEB_DIST] is None

    def test_signer_for_kind_returns_platform(self):
        assert signer_for_kind(BuildArtifactKind.MSI) is SignerType.WINDOWS
        assert signer_for_kind(BuildArtifactKind.APK) is SignerType.ANDROID

    def test_signer_for_kind_returns_none_for_unsigned(self):
        assert signer_for_kind(BuildArtifactKind.DEB) is None


class TestExtensionKind:
    """文件扩展名 → 物理形态映射 (T4 真相源, _detect_sign_targets 读它)。"""

    def test_all_file_kinds_have_extension(self):
        """全登记不变量: 每个文件形态 (除 web_dist 目录形态) 都有扩展名映射。

        新增 IPA/HAP (T5/T8) 时须同步加扩展名, 否则 _detect_sign_targets 漏签。
        """
        file_kinds = {k for k in BuildArtifactKind if k != BuildArtifactKind.WEB_DIST}
        assert set(EXTENSION_KIND.values()) == file_kinds

    def test_msi_exe_route_to_windows(self):
        assert EXTENSION_KIND[".msi"] is BuildArtifactKind.MSI
        assert EXTENSION_KIND[".exe"] is BuildArtifactKind.EXE

    def test_app_routes_to_apple(self):
        """v6.19 T4 补 T2 遗漏: .app → APP → APPLE (macOS bundle, 真相源完整性)。"""
        assert EXTENSION_KIND[".app"] is BuildArtifactKind.APP

    def test_ipa_hap_extensions(self):
        """v6.19 T5/T8: .ipa/.hap 扩展名登记 (签名器实现 T7/T10)。"""
        assert EXTENSION_KIND[".ipa"] is BuildArtifactKind.IPA
        assert EXTENSION_KIND[".hap"] is BuildArtifactKind.HAP

    def test_unsigned_extensions_present_but_skip(self):
        """deb/appimage 在 EXTENSION_KIND (可扫) 但 signer_for_kind=None (不签)。"""
        assert EXTENSION_KIND[".deb"] is BuildArtifactKind.DEB
        assert EXTENSION_KIND[".appimage"] is BuildArtifactKind.APPIMAGE
        assert signer_for_kind(BuildArtifactKind.DEB) is None
        assert signer_for_kind(BuildArtifactKind.APPIMAGE) is None


class TestTargetArtifactKinds:
    def test_all_existing_targets_registered(self):
        """全登记不变量: 每个 BuildTarget 都在 TARGET_ARTIFACT_KINDS 登记。

        新增 BuildTarget (T3 TAURI_WINDOWS / T6 CAPACITOR_IOS / T9 HARMONY_HAP)
        必须同步登记, 否则 target_artifact_kinds 抛 ValueError。
        """
        for target in BuildTarget:
            assert target in TARGET_ARTIFACT_KINDS, (
                f"{target} 未登记产物形态 — 新增 BuildTarget 必须在 "
                f"TARGET_ARTIFACT_KINDS 显式登记"
            )

    def test_tauri_linux_produces_deb_and_appimage(self):
        kinds = target_artifact_kinds(BuildTarget.TAURI_LINUX)
        assert BuildArtifactKind.DEB in kinds
        assert BuildArtifactKind.APPIMAGE in kinds

    def test_web_produces_dist_only(self):
        assert target_artifact_kinds(BuildTarget.WEB) == frozenset({BuildArtifactKind.WEB_DIST})

    def test_capacitor_apk_produces_apk(self):
        assert target_artifact_kinds(BuildTarget.CAPACITOR_APK) == frozenset({BuildArtifactKind.APK})

    def test_tauri_windows_produces_msi_and_exe(self):
        """v6.19 T3: TAURI_WINDOWS 产物 .msi + .exe (T2 已建模形态, 走 CI 编排)。"""
        kinds = target_artifact_kinds(BuildTarget.TAURI_WINDOWS)
        assert BuildArtifactKind.MSI in kinds
        assert BuildArtifactKind.EXE in kinds
        assert len(kinds) == 2

    def test_capacitor_ios_produces_ipa(self):
        """v6.19 T6: CAPACITOR_IOS 产物 .ipa (T5 已建模形态, 走 CI 编排)。"""
        kinds = target_artifact_kinds(BuildTarget.CAPACITOR_IOS)
        assert kinds == frozenset({BuildArtifactKind.IPA})

    def test_harmony_hap_produces_hap(self):
        """v6.19 T9: HARMONY_HAP 产物 .hap (T8 已建模形态, 走 CI 编排)。"""
        kinds = target_artifact_kinds(BuildTarget.HARMONY_HAP)
        assert kinds == frozenset({BuildArtifactKind.HAP})

    def test_unregistered_target_raises_value_error(self, monkeypatch):
        """新增 BuildTarget 漏登记 TARGET_ARTIFACT_KINDS 时, 查询抛 ValueError。"""
        reduced = {
            k: v for k, v in TARGET_ARTIFACT_KINDS.items() if k != BuildTarget.WEB
        }
        monkeypatch.setattr(
            "arc.domain.artifact.value_objects.TARGET_ARTIFACT_KINDS", reduced
        )
        with pytest.raises(ValueError, match="未登记产物形态"):
            target_artifact_kinds(BuildTarget.WEB)


class TestCrossSourceConsistency:
    """跨真相源一致性: BuildTarget 的两处登记必须同步 (T3 加 target 时守护)。

    - execution_backend.TARGET_BACKENDS (执行后端 DOCKER/CI)
    - artifact.TARGET_ARTIFACT_KINDS (产物形态集合)
    新增 BuildTarget 漏登记任一处, 对应查询抛 ValueError。本测试确保两真相源
    覆盖的 BuildTarget 集合完全一致 — 防止 T3 只登记 TARGET_BACKENDS 忘记
    TARGET_ARTIFACT_KINDS (反之亦然), 导致 target 能路由执行后端却查不到产物形态。
    """

    def test_both_sources_cover_same_targets(self):
        backend_targets = set(TARGET_BACKENDS.keys())
        kinds_targets = set(TARGET_ARTIFACT_KINDS.keys())
        assert backend_targets == kinds_targets, (
            f"双真相源 BuildTarget 集合不一致: "
            f"TARGET_BACKENDS={backend_targets} TARGET_ARTIFACT_KINDS={kinds_targets}"
        )

    def test_every_target_resolves_both_sources(self):
        """每个 BuildTarget 都能从两真相源成功查询 (不抛 ValueError)。"""
        for target in BuildTarget:
            target_execution_backend(target)  # 不抛 = 已登记 backend
            target_artifact_kinds(target)  # 不抛 = 已登记形态
