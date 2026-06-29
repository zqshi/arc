"""Tests for domain/sandbox/execution_backend — target→backend 路由单一真相源。

domain 层零 mock: 直接查表/构造, 验证映射 + 全登记不变量 + 未登记抛错契约。
"""

import pytest

from arc.domain.sandbox.execution_backend import (
    CI_RUNNER_KIND,
    TARGET_BACKENDS,
    BuildExecutionBackend,
    CIRunnerKind,
    ci_runner_kind,
    target_execution_backend,
)
from arc.domain.sandbox.value_objects import BuildTarget


class TestTargetExecutionBackend:
    def test_existing_linux_targets_route_to_docker(self):
        """现有三 target 全 DOCKER (容器内构建, Agent run_command)。"""
        assert target_execution_backend(BuildTarget.TAURI_LINUX) is BuildExecutionBackend.DOCKER
        assert target_execution_backend(BuildTarget.WEB) is BuildExecutionBackend.DOCKER
        assert target_execution_backend(BuildTarget.CAPACITOR_APK) is BuildExecutionBackend.DOCKER

    def test_tauri_windows_routes_to_ci(self):
        """v6.19 T3: TAURI_WINDOWS 走 CI 编排 (windows runner, 需原生 OS, 非容器)。"""
        assert target_execution_backend(BuildTarget.TAURI_WINDOWS) is BuildExecutionBackend.CI

    def test_capacitor_ios_routes_to_ci(self):
        """v6.19 T6: CAPACITOR_IOS 走 CI 编排 (macos runner + xcodebuild, 非容器)。"""
        assert target_execution_backend(BuildTarget.CAPACITOR_IOS) is BuildExecutionBackend.CI

    def test_harmony_hap_routes_to_ci(self):
        """v6.19 T9: HARMONY_HAP 走 CI 编排 (DevEco CLT + hvigorw, 非容器)。"""
        assert target_execution_backend(BuildTarget.HARMONY_HAP) is BuildExecutionBackend.CI

    def test_all_enumerated_targets_registered(self):
        """全登记不变量: BuildTarget 枚举每个值都在 TARGET_BACKENDS 登记。

        新增 BuildTarget (windows/ios/harmony) 必须同步登记 backend, 否则此处
        断言失败 — 阻止"只改枚举不登记"在编译/测试期暴露, 而非运行时静默走错后端。
        """
        for target in BuildTarget:
            assert target in TARGET_BACKENDS, (
                f"{target} 未登记执行后端 — 新增 BuildTarget 必须同步 "
                f"domain/sandbox/execution_backend.py TARGET_BACKENDS"
            )

    def test_unregistered_target_raises_value_error(self, monkeypatch):
        """新增 BuildTarget 漏登记 TARGET_BACKENDS 时, 查询抛 ValueError。

        模拟"枚举加了新值但 TARGET_BACKENDS 漏登记"的真实场景: 临时移除一个
        映射项, 验证对应 target 查询抛错 (而非静默 fallback 到某默认后端)。
        """
        reduced = {
            k: v for k, v in TARGET_BACKENDS.items() if k != BuildTarget.WEB
        }
        monkeypatch.setattr(
            "arc.domain.sandbox.execution_backend.TARGET_BACKENDS", reduced
        )
        with pytest.raises(ValueError, match="未登记执行后端"):
            target_execution_backend(BuildTarget.WEB)


class TestBuildExecutionBackend:
    def test_backend_values_are_stable_strings(self):
        """后端枚举值是稳定字符串 (供配置/日志/前端契约引用)。"""
        assert BuildExecutionBackend.DOCKER.value == "docker"
        assert BuildExecutionBackend.CI.value == "ci"


class TestCIRunnerKind:
    def test_values_are_stable_strings(self):
        assert CIRunnerKind.HOSTED.value == "hosted"
        assert CIRunnerKind.SELF_HOSTED_NEEDED.value == "self_hosted_needed"

    def test_all_ci_targets_registered(self):
        """全登记不变量: 每个 CI target 都在 CI_RUNNER_KIND 登记 (T11 就绪检测守护)。"""
        for target in BuildTarget:
            if target_execution_backend(target) is BuildExecutionBackend.CI:
                assert target in CI_RUNNER_KIND, (
                    f"CI target {target} 未登记 runner 特性 — 新增 CI target 必须在 "
                    f"CI_RUNNER_KIND 显式登记 (HOSTED/SELF_HOSTED_NEEDED)"
                )

    def test_windows_and_ios_hosted_harmony_self_hosted(self):
        assert ci_runner_kind(BuildTarget.TAURI_WINDOWS) is CIRunnerKind.HOSTED
        assert ci_runner_kind(BuildTarget.CAPACITOR_IOS) is CIRunnerKind.HOSTED
        assert ci_runner_kind(BuildTarget.HARMONY_HAP) is CIRunnerKind.SELF_HOSTED_NEEDED

    def test_docker_target_query_raises(self):
        """DOCKER target 不在 CI_RUNNER_KIND, 查询抛 ValueError (调用方应先判 backend)。"""
        with pytest.raises(ValueError, match="未登记 runner 特性"):
            ci_runner_kind(BuildTarget.TAURI_LINUX)

    def test_unregistered_ci_target_raises(self, monkeypatch):
        """CI target 漏登记 CI_RUNNER_KIND 时查询抛 ValueError。"""
        reduced = {k: v for k, v in CI_RUNNER_KIND.items() if k != BuildTarget.TAURI_WINDOWS}
        monkeypatch.setattr("arc.domain.sandbox.execution_backend.CI_RUNNER_KIND", reduced)
        with pytest.raises(ValueError, match="未登记 runner 特性"):
            ci_runner_kind(BuildTarget.TAURI_WINDOWS)
