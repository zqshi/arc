"""CI 编排基础设施 — GHA Actions API client (v6.19 T3)。

为 BuildOrchestrationService 提供 GHA Actions API 封装。与 infrastructure/github_client.py
(Issue/PR 协作域) 分模块: Actions 是 CI 构建编排域 (workflow dispatch/run/artifact)。
"""
from arc.infrastructure.ci.github_actions_client import GitHubActionsClient

__all__ = ["GitHubActionsClient"]
