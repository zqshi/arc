"""Tests for domain/sandbox/execution_backend — target→backend 路由单一真相源。

domain 层零 mock: 直接查表/构造, 验证映射 + 全登记不变量 + 未登记抛错契约。
"""

import pytest

from arc.domain.sandbox.execution_backend import (
    TARGET_BACKENDS,
    BuildExecutionBackend,
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
