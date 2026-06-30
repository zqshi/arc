"""Agent 任务耗时指标 (application 层, v6.19 续7补 A3)。

放在 application 层而非 interface/middleware/metrics.py, 因埋点方在 application/execution
(DDD: application 禁止 import interface)。prometheus_client 全局注册表, 定义位置不限,
/metrics 端点 generate_latest 自动收集全部指标 (含此处定义)。
"""

from __future__ import annotations

from prometheus_client import Histogram

AGENT_TASK_DURATION = Histogram(
    "arc_agent_task_duration_seconds",
    "Agent autopilot 任务耗时 (秒), outcome=complete/paused/timeout/error",
    ["outcome"],
)
