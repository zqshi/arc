"""CI 构建编排域 (v6.19 T3)。

BuildOrchestrationService 编排 CI target (windows/ios/harmony) 的构建: 触发 GHA
workflow → 轮询 → 下载产物 → 接入 BUILD artifact 锚点。与 DockerSandboxRuntime (DOCKER
target, Agent 同步构建) 并列, 由 target_execution_backend(target) 路由 (T1 真相源)。
"""
from arc.application.build.orchestration import BuildOrchestrationService

__all__ = ["BuildOrchestrationService"]
