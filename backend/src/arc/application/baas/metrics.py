"""BaaS provision 指标 (application 层, v6.19 续9 运维可观测)。

放在 application 层而非 interface/middleware/metrics.py, 因埋点方在
application/execution/artifact_post_process.py (DDD: application 禁止 import interface)。
prometheus_client 全局注册表, /metrics 端点 generate_latest 自动收集。

指标:
- BAAS_PROVISION_TOTAL: provision 触发计数 (result=success|skip|fail + reason)
  运维看失败率/skip 分布 (模型无聚合是高频正常 skip, 其他 reason 异常)。
- BAAS_PROVISION_DURATION: provision→apply_model 全链路耗时 (秒)。
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

BAAS_PROVISION_TOTAL = Counter(
    "arc_baas_provision_total",
    "BaaS provision 触发次数 (领域模型提取后自动装配)",
    ["result", "reason"],
    # reason 枚举: success / skip_no_aggregates / skip_no_project / skip_no_domain_model /
    # fail_provision / fail_apply / fail_other
)

BAAS_PROVISION_DURATION = Histogram(
    "arc_baas_provision_duration_seconds",
    "BaaS provision→apply_model 全链路耗时 (秒)",
)
