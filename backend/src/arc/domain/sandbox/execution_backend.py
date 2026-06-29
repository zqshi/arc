"""构建执行后端路由 — BuildTarget → 执行后端 (DOCKER / CI) 单一真相源。

v6.19 T1 架构决策 (方案 A: CI 编排):
- 现有 linux 系 target (tauri_linux/web/capacitor_apk) 走 DockerSandboxRuntime —
  Agent 在容器内 run_command 执行构建, 产物落挂载目录 (RW 挂载, v6.0 决策)。
- 新平台 target (windows/ios/harmony) 需原生 OS runner (WebView2/Xcode/DevEco),
  Linux 容器无法构建。这些 target **不进 SandboxRuntime ABC** (其契约是
  run_command -> str 同步单命令返回输出, 与 GHA workflow_dispatch 异步 batch 产物
  收集语义错配; 产物是 .msi/.ipa 文件而非 stdout 字符串), 而走 CI 编排器:
  触发 GHA workflow_dispatch → 轮询 run → 下载 artifact → 接入 BUILD artifact 锚点
  (ArtifactService.create_or_update_build, v6.9), 与 docker 构建产物同走一条
  构建→签名→分发链路。

本模块是 target→backend 路由的单一真相源:
- 新增 BuildTarget 必须在此显式登记 backend, 否则 target_execution_backend()
  抛 ValueError (强制登记, v6.15 硬不变量精神, 禁止"只改枚举不登记")。
- 调用方 (构建入口) 读 target_execution_backend(target) 决定走 docker runtime
  还是 CI 编排, 路由逻辑不散落多处 if/else。
- 不在 SandboxPolicy 加字段 — CI 编排不进 sandbox 体系, 路由读独立真相源,
  避免 CI 信息污染 docker 专属配置类。

domain 层零外部依赖: 仅 import 同域 BuildTarget, 纯枚举 + dict + 查询函数。
"""
from __future__ import annotations

from enum import StrEnum

from arc.domain.sandbox.value_objects import BuildTarget


class BuildExecutionBackend(StrEnum):
    """构建产物的执行后端。

    DOCKER: DockerSandboxRuntime 容器内构建 (linux 系 target, Agent run_command)。
    CI: GHA matrix job 编排构建 (windows/ios/harmony, 需原生 OS runner)。
    """

    DOCKER = "docker"
    CI = "ci"


# BuildTarget → 执行后端。显式全登记, 新增 target 必须同步此处。
# v6.19: 现有三 target DOCKER; TAURI_WINDOWS CI 编排 (windows runner, 需原生 OS)。
TARGET_BACKENDS: dict[BuildTarget, BuildExecutionBackend] = {
    BuildTarget.TAURI_LINUX: BuildExecutionBackend.DOCKER,
    BuildTarget.WEB: BuildExecutionBackend.DOCKER,
    BuildTarget.CAPACITOR_APK: BuildExecutionBackend.DOCKER,
    BuildTarget.TAURI_WINDOWS: BuildExecutionBackend.CI,
}


def target_execution_backend(target: BuildTarget) -> BuildExecutionBackend:
    """查询 target 的执行后端 (单一真相源)。

    新增 BuildTarget 漏登记时抛 ValueError, 强制同步 TARGET_BACKENDS —
    否则新 target 会静默走错后端 (如 CI target 落 docker 必构建失败),
    显式报错优于运行时失败。

    Raises:
        ValueError: target 未在 TARGET_BACKENDS 登记 (新增 BuildTarget 漏登记)。
    """
    try:
        return TARGET_BACKENDS[target]
    except KeyError as exc:
        raise ValueError(
            f"BuildTarget {target} 未登记执行后端 — 新增 BuildTarget 必须在 "
            f"domain/sandbox/execution_backend.py TARGET_BACKENDS 显式登记 "
            f"(DOCKER 或 CI), 禁止只改枚举不登记"
        ) from exc
