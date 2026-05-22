"""Seed data for Project 5: 开发者开放平台
3 versions, v1.0/v2.0 each with 2 full-pipeline todos, v3.0 planning.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ═══════════════════════════════════════════════════════════════
# Todo1: API限流与熔断 (v1.0, done)
# ═══════════════════════════════════════════════════════════════

T1_REQ = {
    "background": "开放平台API无保护机制，单个恶意应用可耗尽全部资源导致平台宕机。去年双11期间某接入方异常重试导致网关CPU 100%，影响所有开发者。需要实现限流与熔断能力保障平台稳定性。",
    "user_scenarios": "1. 平台管理员在控制台为每个API设置限流规则（QPS上限、突发容量）\n2. 开发者调用API时，超过限流阈值返回429状态码和重试建议\n3. 某API下游服务异常时自动熔断，返回降级响应\n4. 熔断恢复后自动进入半开状态，逐步放量\n5. 管理员查看限流和熔断的实时仪表盘",
    "goals": "- 支持按应用+接口粒度的限流配置\n- 令牌桶算法，支持突发流量\n- 熔断阈值：5秒内错误率>50%触发，30秒后半开\n- 限流响应延迟增加<2ms\n- 支持动态调整限流参数（热更新，不重启）",
    "boundaries": "- 不做分布式限流（单机限流+Redis计数器即可）\n- 不做按用户粒度限流（按应用粒度）\n- 不做自适应限流（固定阈值）\n- 熔断不做链路级传播",
    "acceptance_criteria": "1. 单应用QPS超过阈值后100%返回429\n2. 令牌桶突发容量正确（桶满时允许burst）\n3. 下游错误率>50%时5秒内触发熔断\n4. 熔断30秒后自动半开，成功则关闭\n5. 限流规则热更新<3秒生效\n6. 限流本身延迟增加<2ms",
    "risk_assessment": "- Redis单点故障导致限流失效：降级为本地计数器\n- 令牌桶精度问题：使用lua脚本保证原子性\n- 熔断误触发：设置最小请求数阈值（5秒内至少20次请求才判断错误率）",
}

T1_UI = {
    "flow_diagram": "graph TD\n    A[API请求到达网关] --> B{限流检查}\n    B -->|通过| C{熔断检查}\n    B -->|超限| D[返回429]\n    C -->|正常| E[转发到下游服务]\n    C -->|熔断中| F[返回降级响应]\n    C -->|半开| G[放行部分请求]\n    E --> H{下游响应}\n    H -->|成功| I[返回结果]\n    H -->|失败| J[记录错误]\n    J --> K{错误率检查}\n    K -->|超阈值| L[触发熔断]\n    K -->|正常| I\n    G --> H\n    L --> F",
    "wireframes": [
        {
            "page_name": "限流规则配置页",
            "description": "管理员为每个API接口配置限流参数和熔断策略",
            "html": '<div class="min-h-screen bg-gray-900 p-6"><div class="max-w-4xl mx-auto"><h1 class="text-xl font-bold text-white mb-6">限流规则配置</h1><div class="bg-gray-800 rounded-lg p-5 mb-4"><div class="flex items-center justify-between mb-4"><h2 class="text-sm font-medium text-gray-400">API: /v1/users/query</h2><span class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs">生效中</span></div><div class="grid grid-cols-3 gap-4"><div><label class="block text-xs text-gray-500 mb-1">QPS上限</label><input type="number" value="1000" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /></div><div><label class="block text-xs text-gray-500 mb-1">突发容量</label><input type="number" value="200" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /></div><div><label class="block text-xs text-gray-500 mb-1">熔断错误率阈值</label><input type="number" value="50" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /></div></div><div class="mt-4 flex gap-3"><button class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">保存并热更新</button><button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md text-sm">重置</button></div></div><div class="bg-gray-800 rounded-lg p-5"><h2 class="text-sm font-medium text-gray-400 mb-3">当前限流状态</h2><div class="grid grid-cols-4 gap-4 text-center"><div class="bg-gray-900 rounded-lg p-3"><p class="text-2xl font-bold text-white">847</p><p class="text-xs text-gray-500 mt-1">当前QPS</p></div><div class="bg-gray-900 rounded-lg p-3"><p class="text-2xl font-bold text-yellow-400">23</p><p class="text-xs text-gray-500 mt-1">被限流/分钟</p></div><div class="bg-gray-900 rounded-lg p-3"><p class="text-2xl font-bold text-green-400">关闭</p><p class="text-xs text-gray-500 mt-1">熔断状态</p></div><div class="bg-gray-900 rounded-lg p-3"><p class="text-2xl font-bold text-white">1.2ms</p><p class="text-xs text-gray-500 mt-1">限流延迟</p></div></div></div></div></div>',
        },
    ],
    "component_specs": [
        {
            "name": "RateLimitConfig",
            "purpose": "限流参数配置表单",
            "behavior": "修改后点击保存热更新到网关",
            "states": "default / saving / saved / error",
        },
        {
            "name": "CircuitBreakerStatus",
            "purpose": "熔断状态指示器",
            "behavior": "实时显示熔断状态：关闭/打开/半开",
            "states": "closed(green) / open(red) / half-open(yellow)",
        },
        {
            "name": "RealTimeMetrics",
            "purpose": "实时QPS和限流计数",
            "behavior": "WebSocket推送，每秒刷新",
            "states": "loading / connected / disconnected",
        },
    ],
    "interaction_rules": "1. 限流参数修改需二次确认\n2. 热更新成功后显示toast通知\n3. 熔断状态变化时闪烁提示\n4. 仪表盘数据每秒自动刷新",
    "responsive_notes": "桌面端管理后台，最小宽度1280px。指标卡片响应式2-4列。",
}

T1_ARCH = {
    "architecture_overview": "基于令牌桶+熔断器的API网关保护层，Go实现高性能限流中间件。\n\n三层架构：\n1. 限流层 (Rate Limiter) — 令牌桶算法\n   - 本地令牌桶：每个app_id+api_path一个桶\n   - Redis计数器：分布式场景下的精确计数\n   - Lua脚本保证令牌获取原子性\n\n2. 熔断层 (Circuit Breaker) — 滑动窗口统计\n   - 5秒滑动窗口，统计错误率\n   - 三状态机：Closed → Open → HalfOpen → Closed\n   - 最小请求数阈值：窗口内<20次请求不触发\n\n3. 配置中心 (Config) — 动态配置热更新\n   - Redis pub/sub 通知配置变更\n   - 本地缓存+版本号校验\n   - 降级策略：Redis不可用时使用本地默认值",
    "data_model": "rate_limit_rules 表:\n  - id: UUID, app_id: FK, api_path: VARCHAR(500)\n  - qps_limit: INT, burst_capacity: INT\n  - circuit_breaker_threshold: FLOAT DEFAULT 0.5\n  - circuit_breaker_timeout: INT DEFAULT 30\n  - enabled: BOOLEAN DEFAULT true\n\nrate_limit_logs 表 (时序数据):\n  - timestamp: TIMESTAMPTZ, app_id: UUID\n  - api_path: VARCHAR, request_count: INT\n  - rejected_count: INT, circuit_state: VARCHAR",
    "api_design": "POST /api/admin/rate-limits — 创建限流规则\nPUT /api/admin/rate-limits/:id — 更新规则(热更新)\nGET /api/admin/rate-limits — 规则列表\nGET /api/admin/rate-limits/:id/metrics — 实时指标\nDELETE /api/admin/rate-limits/:id — 删除规则\nGET /api/admin/circuit-breakers — 熔断状态总览",
    "tech_decisions": [
        {
            "decision": "限流算法",
            "chosen": "令牌桶而非漏桶",
            "reason": "令牌桶允许突发流量，更适合API网关场景",
        },
        {
            "decision": "计数器存储",
            "chosen": "Redis + 本地缓存双层",
            "reason": "Redis保证分布式精确性，本地缓存兜底Redis故障",
        },
        {
            "decision": "熔断实现",
            "chosen": "自研而非Sentinel",
            "reason": "Go生态下Sentinel成熟度不够，且需求简单可自研",
        },
    ],
    "implementation_plan": "Phase 1: 令牌桶核心 (2天)\n  - 本地令牌桶实现+单元测试\n  - Redis Lua脚本原子操作\n\nPhase 2: 熔断器 (2天)\n  - 滑动窗口错误率统计\n  - 三状态机+半开探测\n\nPhase 3: 配置热更新 (1天)\n  - Redis pub/sub 监听\n  - 管理API + 配置下发\n\nPhase 4: 可观测性 (1天)\n  - Prometheus metrics 暴露\n  - Grafana 仪表盘模板",
}

T1_DEV = {
    "execution_log": "$ go test ./pkg/ratelimit/ -v -count=1\n=== RUN   TestTokenBucket_Allow\n--- PASS: TestTokenBucket_Allow (0.00s)\n=== RUN   TestTokenBucket_Burst\n--- PASS: TestTokenBucket_Burst (0.01s)\n=== RUN   TestTokenBucket_Refill\n--- PASS: TestTokenBucket_Refill (1.01s)\n=== RUN   TestCircuitBreaker_Open\n--- PASS: TestCircuitBreaker_Open (0.00s)\n=== RUN   TestCircuitBreaker_HalfOpen\n--- PASS: TestCircuitBreaker_HalfOpen (5.02s)\n=== RUN   TestRedisLimiter_Atomic\n--- PASS: TestRedisLimiter_Atomic (0.03s)\nPASS\nok  gateway/pkg/ratelimit 6.12s\n\n$ go build -o bin/gateway ./cmd/gateway\nBuild successful\n\n$ wrk -t4 -c100 -d10s http://localhost:8080/v1/test\nRunning 10s test\n  4 threads and 100 connections\n  Thread Stats   Avg      Stdev     Max\n    Latency     1.23ms   0.45ms   8.21ms\n  Requests/sec: 12847.32\n  Transfer/sec: 2.31MB",
    "code_changes": [
        "pkg/ratelimit/token_bucket.go — 令牌桶核心算法实现",
        "pkg/ratelimit/circuit_breaker.go — 熔断器状态机",
        "pkg/ratelimit/redis_limiter.go — Redis分布式计数器+Lua脚本",
        "pkg/ratelimit/middleware.go — gin中间件集成",
        "internal/config/hot_reload.go — Redis pub/sub配置热更新",
        "api/admin/ratelimit_handler.go — 管理端API",
        "scripts/lua/token_bucket.lua — Redis原子令牌获取脚本",
    ],
    "test_results": "32/32 tests passed | Line coverage: 91.3% | Branch coverage: 82.1% | Duration: 6.12s",
    "decisions_made": [
        {
            "decision": "令牌桶用sync.Mutex而非channel",
            "reason": "Mutex在高并发下性能更好，channel有goroutine调度开销",
        },
        {
            "decision": "熔断窗口用环形buffer而非时间切片",
            "reason": "内存固定、无GC压力，适合高QPS场景",
        },
        {"decision": "Lua脚本内嵌Go代码而非外部文件", "reason": "部署简单，go:embed编译期打包"},
    ],
}

T1_TEST = {
    "criteria_verification": [
        {
            "criteria": "单应用QPS超过阈值后100%返回429",
            "status": "pass",
            "evidence": "设置QPS=100，发送200 req/s，稳定100个返回200、100个返回429",
        },
        {
            "criteria": "令牌桶突发容量正确",
            "status": "pass",
            "evidence": "burst=50，静默5秒后瞬间发送150请求，前150个全部通过（100+50burst）",
        },
        {
            "criteria": "下游错误率>50%时5秒内触发熔断",
            "status": "pass",
            "evidence": "模拟下游60%错误率，4.8秒后熔断器状态变为Open",
        },
        {
            "criteria": "熔断30秒后自动半开",
            "status": "pass",
            "evidence": "熔断触发后30秒，状态变为HalfOpen，放行1个探测请求",
        },
        {
            "criteria": "限流规则热更新<3秒生效",
            "status": "pass",
            "evidence": "通过API修改QPS阈值，1.2秒后新阈值生效",
        },
        {
            "criteria": "限流延迟增加<2ms",
            "status": "pass",
            "evidence": "压测对比：无限流P99=0.8ms，有限流P99=1.23ms，增加0.43ms",
        },
    ],
    "issues_found": [
        {
            "description": "Redis连接断开后本地降级切换有200ms延迟",
            "severity": "low",
            "suggestion": "可接受，已添加连接池健康检查减少发生概率",
        },
        {
            "description": "熔断半开状态下并发探测请求可能超过1个",
            "severity": "medium",
            "suggestion": "已通过atomic.CompareAndSwap修复，保证单个探测",
        },
    ],
    "coverage_summary": "总计 32 个测试用例，全部通过\n- 令牌桶算法测试: 12/12 passed\n- 熔断器状态机测试: 8/8 passed\n- Redis分布式限流测试: 6/6 passed\n- 集成测试: 4/4 passed\n- 压力测试: 2/2 passed\n\n代码覆盖率: Line 91.3% | Branch 82.1%\n执行耗时: 42 秒",
}

T1_DEPLOY = {
    "service_url": "https://gateway.openapi.example.com",
    "health_check_result": "All checks passed — Gateway latency P99=1.2ms, Redis connected, Circuit breakers all closed",
    "deploy_log": '$ docker build -t gateway:v1.0.0 -f deploy/Dockerfile .\n[OK] Image built: gateway:v1.0.0 (43MB)\n\n$ kubectl apply -f deploy/k8s/\n[OK] ConfigMap/gateway-config created\n[OK] Deployment/gateway updated (3 replicas)\n[OK] Service/gateway-svc created\n[OK] HPA/gateway configured (min=3, max=10)\n\n$ kubectl rollout status deployment/gateway\ndeployment "gateway" successfully rolled out\n\n$ curl -s https://gateway.openapi.example.com/health | jq .\n{"status":"ok","redis":"connected","uptime":"1m12s"}\n\n冒烟测试: 限流拦截 ✓ | 熔断触发 ✓ | 热更新 ✓ | 降级兜底 ✓',
    "rollback_plan": "1. kubectl rollout undo deployment/gateway\n2. 限流规则回滚：Redis中保留前版本配置快照\n3. 如Redis异常：网关自动降级为本地默认限流\n\n已通知SRE团队监控Grafana面板，异常自动告警。",
}

T1_EXP = {
    "problem": "令牌桶算法在Go高并发下的锁竞争导致P99延迟飙升，初版实现用RWMutex但写锁（令牌消耗）频率极高，读写比接近1:1时RWMutex退化为Mutex。",
    "solution": "分两步优化：1) 改用sync.Mutex替代RWMutex（写多读少场景Mutex更快）；2) 按app_id分桶，每个桶独立锁，消除跨应用竞争。优化后P99从4.2ms降至1.2ms。",
    "decisions": [
        {
            "point": "锁类型选择",
            "chosen": "sync.Mutex而非RWMutex",
            "reason": "令牌消耗是写操作，频率高，RWMutex的写锁反而比Mutex慢15%",
        },
        {
            "point": "熔断器实现",
            "chosen": "环形buffer统计而非时间切片",
            "reason": "内存固定O(1)，无GC压力，适合高QPS网关场景",
        },
    ],
    "pitfalls": [
        {
            "issue": "RWMutex在写多场景下性能反而更差",
            "cause": "RWMutex的写锁需要等待所有读锁释放，写频率高时退化严重",
            "fix": "Benchmark对比后选择Mutex，写多读少场景永远选Mutex",
        },
        {
            "issue": "熔断半开状态并发探测",
            "cause": "多个goroutine同时检测到HalfOpen并发送探测请求",
            "fix": "用atomic.CompareAndSwap保证只有一个goroutine执行探测",
        },
    ],
    "applicable_scenarios": "高QPS API网关的限流保护，Go微服务的熔断降级。令牌桶适合允许突发的场景，漏桶适合严格匀速。",
    "tags": ["限流", "熔断", "Go并发", "性能优化"],
}

T1_CLAR_MSGS = [
    (
        "assistant",
        "你好！我来帮你梳理「API限流与熔断」的需求。\n\n先聊背景——为什么现在要做限流？是出过线上事故还是预防性建设？",
    ),
    (
        "user",
        "出过事故。去年双11某个接入方的SDK有bug，异常重试直接把网关CPU打到100%，影响了所有开发者将近20分钟。当时只能手动封IP，太被动了。",
    ),
    (
        "assistant",
        "这是典型的缺乏流量保护导致的级联故障。需要两层防御：\n1. 限流——控制每个应用的请求速率\n2. 熔断——下游异常时快速失败\n\n限流的粒度怎么定？按应用、按接口、还是按用户？",
    ),
    (
        "user",
        "按应用+接口的组合粒度。比如应用A调用/v1/users接口限制1000 QPS，调用/v1/orders限制500 QPS。不需要按终端用户粒度。",
    ),
    (
        "assistant",
        "明白。限流算法倾向哪种？\n- 令牌桶：允许突发流量，适合API场景\n- 漏桶：严格匀速，适合背压场景\n- 滑动窗口：实现简单但不支持突发",
    ),
    (
        "user",
        "令牌桶，需要允许突发。比如平时500QPS的接口，偶尔突发到700应该允许通过。另外限流参数要支持动态调整，不能每次改了重启网关。",
    ),
    (
        "assistant",
        "好的。确认需求：\n- 令牌桶算法，按应用+接口粒度\n- 支持突发容量配置\n- 参数热更新（不重启）\n- 熔断：5秒窗口错误率>50%触发，30秒后半开\n- 限流本身延迟<2ms\n\n需求清晰，进入设计阶段。",
    ),
    ("user", "确认。"),
]

T1_UI_MSGS = [
    ("assistant", "开始设计限流管理的交互方案。管理员需要在哪里配置限流规则？"),
    (
        "user",
        "在开放平台管理后台，一个独立的限流配置页面。能看到所有API的限流规则，点进去修改参数，保存后立即生效。还需要看到实时的限流数据。",
    ),
    (
        "assistant",
        "方案设计：\n\n**限流规则配置页**\n- 顶部：API列表，每行显示接口路径、当前QPS、限流规则状态\n- 详情区：QPS上限、突发容量、熔断阈值三个输入框\n- 底部：实时指标卡片（当前QPS、被限流数/分钟、熔断状态、限流延迟）\n- 保存按钮触发热更新，成功后toast提示\n\n流程图和线框图已生成。",
    ),
    ("user", "可以，简洁实用。"),
]

T1_ARCH_MSGS = [
    (
        "assistant",
        "进入架构设计。核心问题：令牌桶的计数器放哪里？\n1. 纯本地内存——性能最好但多实例不共享\n2. 纯Redis——精确但每次请求一次网络IO\n3. 本地+Redis双层——本地粗控+Redis精确计数",
    ),
    (
        "user",
        "双层方案。网关是多实例部署的，纯本地不准确。但每个请求都查Redis太慢了，本地做一层缓存兜底。",
    ),
    (
        "assistant",
        "同意。架构方案：\n\n**限流层**：本地令牌桶（Mutex+per-bucket锁）+ Redis Lua脚本精确计数\n- 本地桶做快速判断，Redis做精确限流\n- Redis不可用时降级为纯本地\n\n**熔断层**：环形buffer滑动窗口\n- 5秒窗口，1秒一个slot，统计错误率\n- 最小请求数阈值：20次/窗口\n\n**配置热更新**：Redis pub/sub\n- 管理API写入DB + 发布变更事件\n- 网关订阅事件，更新本地配置缓存\n\n方案确认？",
    ),
    ("user", "确认，就这个方案。重点关注Redis故障的降级逻辑。"),
]

T1_EXT_MSGS = [
    (
        "assistant",
        "限流与熔断已上线运行一周，数据稳定。来沉淀经验。\n\n这次实现过程中最值得记录的点？",
    ),
    (
        "user",
        "两个：一是Go里RWMutex在写多场景反而比Mutex慢，这个坑不明显；二是熔断半开状态的并发探测问题，不用CAS会导致多个探测请求同时打到下游。",
    ),
    (
        "assistant",
        "提炼两个关键经验：\n\n**经验1: Go并发锁选型**\n- RWMutex适合读多写少，令牌桶消耗是高频写，Mutex更快\n- 分桶独立锁消除跨应用竞争\n\n**经验2: 熔断半开并发控制**\n- atomic.CompareAndSwap保证单个探测\n- 环形buffer比时间切片更省内存\n\n确认归档？",
    ),
    ("user", "确认。"),
]

# ═══════════════════════════════════════════════════════════════
# Todo2: 第三方应用接入 (v1.0, done)
# ═══════════════════════════════════════════════════════════════

T2_REQ = {
    "background": "开放平台需要让第三方开发者能自助注册、创建应用、获取API Key并查看调用统计。目前接入流程全靠邮件沟通+人工开通，平均周期5个工作日，开发者体验极差。",
    "user_scenarios": "1. 开发者在官网注册账号，完成邮箱验证\n2. 登录开发者控制台，创建应用并填写基本信息\n3. 系统自动生成API Key和Secret\n4. 开发者在控制台查看API调用量、成功率、延迟等统计\n5. 管理员审核应用信息，控制上线/下线状态",
    "goals": "- 开发者自助注册到获取API Key < 5分钟\n- 每个应用独立的API Key，支持多Key轮转\n- 调用统计延迟<1分钟（准实时）\n- 应用管理支持上线/下线/吊销操作\n- API Key支持IP白名单绑定",
    "boundaries": "- 不做OAuth2授权码流程（直接API Key鉴权）\n- 不做开发者等级体系（后续版本）\n- 不做API文档自动生成（v3.0规划）\n- 统计数据保留90天",
    "acceptance_criteria": "1. 注册→创建应用→获取Key全流程<5分钟\n2. API Key格式：ak_前缀+32位随机字符\n3. Secret只在创建时展示一次\n4. 调用统计图表准实时（<1分钟延迟）\n5. Key吊销后立即失效（<3秒）\n6. IP白名单生效延迟<5秒",
    "risk_assessment": "- API Key泄露风险：支持一键吊销+重新生成\n- 统计数据量大：按小时聚合+冷数据归档\n- 恶意注册：邮箱验证+人工审核双重防线",
}

T2_UI = {
    "flow_diagram": "graph TD\n    A[开发者注册] --> B[邮箱验证]\n    B --> C[登录控制台]\n    C --> D[创建应用]\n    D --> E[填写应用信息]\n    E --> F[生成API Key + Secret]\n    F --> G[展示Secret-仅一次]\n    G --> H[开始集成开发]\n    H --> I[调用API]\n    I --> J[查看调用统计]\n    C --> K[应用管理]\n    K --> L[Key轮转]\n    K --> M[设置IP白名单]\n    K --> N[查看调用明细]",
    "wireframes": [
        {
            "page_name": "开发者控制台 - 应用概览",
            "description": "展示开发者的应用列表和核心调用指标",
            "html": '<div class="min-h-screen bg-gray-900 p-6"><div class="max-w-5xl mx-auto"><div class="flex items-center justify-between mb-6"><h1 class="text-xl font-bold text-white">我的应用</h1><button class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">+ 创建应用</button></div><div class="grid grid-cols-3 gap-4 mb-6"><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">今日调用量</p><p class="text-2xl font-bold text-white mt-1">128,432</p><p class="text-xs text-green-400 mt-1">↑ 12.3% vs 昨日</p></div><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">成功率</p><p class="text-2xl font-bold text-green-400 mt-1">99.7%</p><p class="text-xs text-gray-500 mt-1">过去24小时</p></div><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">平均延迟</p><p class="text-2xl font-bold text-white mt-1">45ms</p><p class="text-xs text-gray-500 mt-1">P95: 128ms</p></div></div><div class="bg-gray-800 rounded-lg overflow-hidden"><table class="w-full text-left text-sm"><thead><tr class="border-b border-gray-700 text-xs text-gray-500 uppercase"><th class="px-5 py-3">应用名称</th><th class="px-5 py-3">API Key</th><th class="px-5 py-3">今日调用</th><th class="px-5 py-3">状态</th><th class="px-5 py-3">操作</th></tr></thead><tbody class="text-gray-300"><tr class="border-b border-gray-800/50"><td class="px-5 py-3 font-medium">用户画像服务</td><td class="px-5 py-3 font-mono text-xs text-gray-400">ak_3f8a...b2c1</td><td class="px-5 py-3">89,231</td><td class="px-5 py-3"><span class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs">运行中</span></td><td class="px-5 py-3"><button class="text-indigo-400 text-xs">管理</button></td></tr><tr><td class="px-5 py-3 font-medium">数据同步工具</td><td class="px-5 py-3 font-mono text-xs text-gray-400">ak_7d2e...f4a9</td><td class="px-5 py-3">39,201</td><td class="px-5 py-3"><span class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs">运行中</span></td><td class="px-5 py-3"><button class="text-indigo-400 text-xs">管理</button></td></tr></tbody></table></div></div></div>',
        },
        {
            "page_name": "应用详情 - Key管理",
            "description": "管理API Key、Secret和IP白名单",
            "html": '<div class="min-h-screen bg-gray-900 p-6"><div class="max-w-4xl mx-auto"><h1 class="text-xl font-bold text-white mb-2">用户画像服务</h1><p class="text-sm text-gray-400 mb-6">App ID: app_9f3a2b1c</p><div class="bg-gray-800 rounded-lg p-5 mb-4"><h2 class="text-sm font-medium text-gray-400 mb-3">API 凭证</h2><div class="space-y-3"><div class="flex items-center justify-between bg-gray-900 rounded px-4 py-3"><div><p class="text-xs text-gray-500">API Key</p><p class="font-mono text-sm text-white">ak_3f8a9c2d7e1b4f6a8c0d2e4f6a8b0c2d</p></div><div class="flex gap-2"><button class="px-3 py-1 bg-gray-700 text-gray-300 rounded text-xs">复制</button></div></div><div class="flex items-center justify-between bg-gray-900 rounded px-4 py-3"><div><p class="text-xs text-gray-500">API Secret</p><p class="font-mono text-sm text-gray-500">••••••••••••••••</p></div><div class="flex gap-2"><button class="px-3 py-1 bg-red-900/50 text-red-400 rounded text-xs">重新生成</button></div></div></div></div><div class="bg-gray-800 rounded-lg p-5"><h2 class="text-sm font-medium text-gray-400 mb-3">IP 白名单</h2><div class="space-y-2"><div class="flex items-center gap-2"><span class="font-mono text-sm text-white bg-gray-900 rounded px-3 py-1">103.24.56.0/24</span><button class="text-red-400 text-xs">×</button></div><div class="flex items-center gap-2"><span class="font-mono text-sm text-white bg-gray-900 rounded px-3 py-1">10.0.0.0/8</span><button class="text-red-400 text-xs">×</button></div><div class="flex gap-2 mt-2"><input placeholder="添加IP或CIDR" class="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /><button class="px-3 py-2 bg-indigo-600 text-white rounded text-sm">添加</button></div></div></div></div></div>',
        },
    ],
    "component_specs": [
        {
            "name": "AppCard",
            "purpose": "应用概览卡片",
            "behavior": "展示应用状态和核心指标",
            "states": "active / suspended / revoked",
        },
        {
            "name": "ApiKeyDisplay",
            "purpose": "API Key展示与操作",
            "behavior": "复制Key、重新生成Secret",
            "states": "normal / regenerating / copied",
        },
        {
            "name": "IpWhitelist",
            "purpose": "IP白名单管理",
            "behavior": "添加/删除IP规则，实时生效",
            "states": "empty / configured",
        },
        {
            "name": "UsageChart",
            "purpose": "调用量图表",
            "behavior": "按小时/天展示调用量趋势",
            "states": "loading / loaded / empty",
        },
    ],
    "interaction_rules": "1. Secret只在创建时展示一次，之后只显示掩码\n2. 重新生成Secret需要输入密码二次确认\n3. Key吊销操作不可逆，需要二次确认\n4. IP白名单为空时默认允许所有IP",
    "responsive_notes": "开发者控制台桌面端优先，最小1024px。统计图表横向滚动适配。",
}

T2_ARCH = {
    "architecture_overview": "第三方应用接入系统，支持开发者自助注册、应用管理和API Key鉴权。\n\n核心模块：\n1. 开发者账号 — 注册/登录/邮箱验证\n   - 独立于管理后台的开发者身份体系\n   - bcrypt密码哈希 + JWT认证\n\n2. 应用管理 — 创建/编辑/上下线\n   - 每个应用独立的app_id\n   - 支持多环境（sandbox/production）\n\n3. API Key鉴权 — Key生成/验证/吊销\n   - Key格式：ak_ + 32位crypto/rand随机字符\n   - Secret: 64位随机字符，bcrypt存储\n   - 验证：Redis缓存热Key，DB兜底\n\n4. 调用统计 — 准实时指标\n   - 网关日志 → Kafka → 聚合消费者 → PostgreSQL\n   - 按小时预聚合，查询走物化视图",
    "data_model": "developers 表:\n  - id: UUID, email: VARCHAR UNIQUE, hashed_password: TEXT\n  - company_name: VARCHAR, status: ENUM(active/suspended)\n\napplications 表:\n  - id: UUID, developer_id: FK, name: VARCHAR\n  - app_id: VARCHAR UNIQUE, status: ENUM(active/suspended/revoked)\n\napi_keys 表:\n  - id: UUID, application_id: FK\n  - key_prefix: VARCHAR(16), key_hash: TEXT\n  - ip_whitelist: JSONB, is_active: BOOLEAN\n\napi_call_stats 表 (按小时聚合):\n  - app_id: VARCHAR, api_path: VARCHAR, hour: TIMESTAMPTZ\n  - call_count: BIGINT, success_count: BIGINT\n  - avg_latency_ms: FLOAT, p95_latency_ms: FLOAT",
    "api_design": "POST /api/developers/register — 开发者注册\nPOST /api/developers/login — 登录\nPOST /api/apps — 创建应用\nGET /api/apps — 应用列表\nPOST /api/apps/:id/keys — 生成API Key\nDELETE /api/apps/:id/keys/:kid — 吊销Key\nPUT /api/apps/:id/keys/:kid/whitelist — 更新IP白名单\nGET /api/apps/:id/stats — 调用统计",
    "tech_decisions": [
        {
            "decision": "鉴权方式",
            "chosen": "API Key而非OAuth2",
            "reason": "开放平台初期以数据API为主，Key方式集成最简单，开发者5分钟可完成接入",
        },
        {
            "decision": "统计数据存储",
            "chosen": "PostgreSQL物化视图而非时序数据库",
            "reason": "数据量有限（<100应用），复用现有PG减少运维负担",
        },
        {
            "decision": "Key存储方式",
            "chosen": "仅存bcrypt hash，不存明文",
            "reason": "即使数据库泄露也无法恢复Key原文",
        },
    ],
    "implementation_plan": "Phase 1: 开发者身份 (2天)\n  - 注册/登录/邮箱验证\n  - JWT认证中间件\n\nPhase 2: 应用管理 (2天)\n  - CRUD + 状态管理\n  - API Key生成与存储\n\nPhase 3: 鉴权中间件 (1天)\n  - Key验证 + IP白名单\n  - Redis缓存层\n\nPhase 4: 调用统计 (2天)\n  - Kafka消费者 + 按小时聚合\n  - 统计API + 物化视图",
}

T2_DEV = {
    "execution_log": "$ go test ./internal/app/ -v -count=1\n=== RUN   TestCreateApp\n--- PASS: TestCreateApp (0.02s)\n=== RUN   TestGenerateApiKey\n--- PASS: TestGenerateApiKey (0.15s)\n=== RUN   TestVerifyApiKey\n--- PASS: TestVerifyApiKey (0.12s)\n=== RUN   TestRevokeKey_Immediate\n--- PASS: TestRevokeKey_Immediate (0.03s)\n=== RUN   TestIpWhitelist\n--- PASS: TestIpWhitelist (0.01s)\n=== RUN   TestCallStats_Aggregation\n--- PASS: TestCallStats_Aggregation (1.02s)\nPASS\nok  gateway/internal/app 1.42s\n\n$ go test ./internal/auth/ -v\n=== RUN   TestDeveloperRegister\n--- PASS: (0.22s)\n=== RUN   TestDeveloperLogin\n--- PASS: (0.13s)\n=== RUN   TestEmailVerification\n--- PASS: (0.05s)\n18 passed in 2.84s\n\n$ npm run build --prefix web/developer-console\nvite v5.x building for production...\n✓ 96 modules transformed.\ndist/index.html   0.38 kB\ndist/assets/app.js  124.67 kB\n✓ built in 2.8s",
    "code_changes": [
        "internal/app/service.go — 应用CRUD和状态管理",
        "internal/app/apikey.go — API Key生成(crypto/rand)和验证",
        "internal/auth/developer.go — 开发者注册登录",
        "internal/middleware/apikey_auth.go — API Key鉴权中间件+Redis缓存",
        "internal/stats/aggregator.go — Kafka消费者+按小时聚合",
        "web/developer-console/ — React开发者控制台前端",
        "migrations/002_applications.sql — 应用和Key表结构",
    ],
    "test_results": "38/38 tests passed | Line coverage: 87.6% | Branch coverage: 79.3% | Duration: 4.26s",
    "decisions_made": [
        {
            "decision": "Key格式用ak_前缀便于识别和日志过滤",
            "reason": "运维可通过前缀快速判断Key类型，也方便git hook扫描防泄露",
        },
        {
            "decision": "Secret用bcrypt而非SHA256存储",
            "reason": "bcrypt有盐值和计算成本，彩虹表攻击无效",
        },
        {
            "decision": "统计聚合用Kafka而非直接写DB",
            "reason": "解耦网关和统计，高QPS时不影响核心链路",
        },
    ],
}

T2_TEST = {
    "criteria_verification": [
        {
            "criteria": "注册→获取Key全流程<5分钟",
            "status": "pass",
            "evidence": "实测从注册到拿到Key耗时2分30秒（含邮箱验证）",
        },
        {
            "criteria": "API Key格式正确",
            "status": "pass",
            "evidence": "生成100个Key，全部符合ak_+32位hex格式",
        },
        {
            "criteria": "Secret只展示一次",
            "status": "pass",
            "evidence": "创建时返回明文，后续查询API只返回前8位+掩码",
        },
        {
            "criteria": "调用统计准实时",
            "status": "pass",
            "evidence": "发起API调用后38秒在统计面板可见",
        },
        {
            "criteria": "Key吊销立即生效",
            "status": "pass",
            "evidence": "吊销后1.2秒Redis缓存失效，后续请求返回401",
        },
        {
            "criteria": "IP白名单生效延迟<5秒",
            "status": "pass",
            "evidence": "更新白名单后2.8秒生效，非白名单IP返回403",
        },
    ],
    "issues_found": [
        {
            "description": "并发创建应用时app_id有极低概率冲突",
            "severity": "low",
            "suggestion": "已添加DB唯一约束+应用层重试，冲突时自动重新生成",
        },
        {
            "description": "统计聚合在Kafka消费延迟时数据不准",
            "severity": "medium",
            "suggestion": "前端统计页面标注'数据延迟约1分钟'，并显示最后更新时间",
        },
    ],
    "coverage_summary": "总计 38 个测试用例，全部通过\n- 开发者账号测试: 8/8 passed\n- 应用管理测试: 10/10 passed\n- API Key鉴权测试: 12/12 passed\n- 调用统计测试: 6/6 passed\n- E2E集成测试: 2/2 passed\n\n代码覆盖率: Line 87.6% | Branch 79.3%\n执行耗时: 38 秒",
}

T2_DEPLOY = {
    "service_url": "https://developer.openapi.example.com",
    "health_check_result": "All checks passed — Developer console responsive, Key verification <5ms, Kafka consumer lag: 0",
    "deploy_log": '$ alembic upgrade head\n[OK] Migration: 002_applications — 创建 applications + api_keys 表\n\n$ docker build -t dev-console:v1.0.0 .\n[OK] Image built: dev-console:v1.0.0 (89MB)\n\n$ kubectl apply -f deploy/k8s/developer/\n[OK] Deployment/dev-console: 2 replicas ready\n[OK] Deployment/stats-aggregator: 1 replica ready\n[OK] Service/dev-console-svc created\n[OK] Ingress/developer.openapi.example.com configured\n\n$ curl -s https://developer.openapi.example.com/health\n{"status":"ok","db":"connected","kafka":"connected","redis":"connected"}\n\n冒烟测试: 注册 ✓ | 创建应用 ✓ | Key验证 ✓ | 统计查询 ✓ | IP白名单 ✓',
    "rollback_plan": "1. kubectl rollout undo deployment/dev-console\n2. kubectl rollout undo deployment/stats-aggregator\n3. 数据库: alembic downgrade -1 (applications表有外键保护)\n4. 已有开发者Key不受影响（Key验证走Redis缓存+DB兜底）\n\n已通知产品团队开始邀请首批内测开发者。",
}

T2_EXP = {
    "problem": "API Key鉴权系统设计中，如何平衡安全性和性能：每次请求都查DB验证Key太慢（P99=15ms），但缓存Key又存在吊销延迟问题。",
    "solution": "三层验证架构：1) 本地LRU缓存（TTL 10s）做热Key快速放行；2) Redis缓存（TTL 60s）做分布式一致性；3) DB做最终兜底。吊销时主动清除Redis缓存+广播invalidate事件，本地缓存自然过期（最多10s延迟，可接受）。",
    "decisions": [
        {
            "point": "Key存储格式",
            "chosen": "仅存bcrypt hash不存明文",
            "reason": "数据库泄露时无法恢复Key原文，安全性最高",
        },
        {
            "point": "缓存策略",
            "chosen": "三层缓存（本地+Redis+DB）",
            "reason": "兼顾性能（<1ms热Key）和安全（吊销<10s生效）",
        },
    ],
    "pitfalls": [
        {
            "issue": "bcrypt验证每次耗时100ms+导致API延迟不可接受",
            "cause": "bcrypt设计目标就是慢，不适合热路径",
            "fix": "首次bcrypt验证通过后，用SHA256(key)做缓存索引，后续走缓存不再bcrypt",
        },
        {
            "issue": "Key吊销后缓存未清导致已吊销Key仍可用",
            "cause": "只清了DB未清Redis和本地缓存",
            "fix": "吊销时三层同步清除：DB标记+Redis DEL+pub/sub广播本地缓存evict",
        },
    ],
    "applicable_scenarios": "API网关Key鉴权、Token验证等高频认证场景。核心原则：热路径走缓存，安全操作走DB，吊销走主动清除。",
    "tags": ["API Key", "鉴权", "缓存策略", "安全"],
}

T2_CLAR_MSGS = [
    (
        "assistant",
        "你好！我来帮你梳理「第三方应用接入」的需求。\n\n目前开发者是怎么接入你们平台的？",
    ),
    (
        "user",
        "现在全靠邮件。开发者发邮件申请，我们人工审核，然后手动在数据库里创建Key发回去。平均5个工作日，开发者反馈很差。",
    ),
    (
        "assistant",
        "5天接入周期确实太长了。核心诉求是自助化：开发者自己注册、创建应用、拿到Key。\n\n几个问题：\n1. 鉴权方式？API Key还是OAuth2？\n2. 需要审核环节吗？\n3. 调用统计是必须的吗？",
    ),
    (
        "user",
        "先用API Key，简单直接。注册不需要审核，但应用上线到生产环境需要人工审核。调用统计必须有，开发者需要看自己的用量。",
    ),
    (
        "assistant",
        "明白。总结需求：\n- 自助注册+邮箱验证\n- 应用创建自动生成Key\n- 生产环境需审核\n- 调用统计准实时\n- Key支持吊销和IP白名单\n\n确认？",
    ),
    ("user", "确认，就这些。注意Secret只能显示一次。"),
]

T2_UI_MSGS = [
    ("assistant", "开始设计开发者控制台的交互方案。核心页面有哪些？"),
    (
        "user",
        "应用列表页是首页，展示我所有应用的概览和核心指标。点进去是应用详情，可以管理Key和看统计。",
    ),
    (
        "assistant",
        "方案：\n\n**应用列表页**\n- 顶部指标卡：今日总调用量、成功率、平均延迟\n- 应用表格：名称、Key前缀、今日调用、状态、操作\n\n**应用详情页**\n- API凭证区：Key展示+复制、Secret掩码+重新生成\n- IP白名单管理：添加/删除CIDR规则\n- 调用统计图表：按小时/天展示趋势\n\nSecret创建时弹窗展示，关闭后不可再查看。线框图已生成。",
    ),
    ("user", "可以。Secret展示弹窗加个复制按钮，提醒开发者妥善保管。"),
]

T2_ARCH_MSGS = [
    (
        "assistant",
        "进入架构设计。核心决策：API Key的验证如何做到高性能？\n\n直接查DB每次15ms，QPS高时不可接受。",
    ),
    ("user", "肯定要缓存。但Key吊销后缓存不清就有安全问题。怎么平衡？"),
    (
        "assistant",
        "三层缓存方案：\n\n1. **本地LRU缓存** (TTL 10s) — 热Key <0.1ms\n2. **Redis缓存** (TTL 60s) — 分布式一致 <1ms\n3. **DB兜底** — 冷Key首次验证\n\n吊销时：DB标记 + Redis DEL + pub/sub广播清本地缓存\n最坏情况：本地缓存TTL 10秒延迟\n\nKey存储方案：只存bcrypt hash，首次验证后用SHA256做缓存索引避免每次bcrypt。\n\n确认？",
    ),
    ("user", "10秒延迟可以接受。确认这个方案。"),
]

T2_EXT_MSGS = [
    (
        "assistant",
        "应用接入系统已上线，首批10个开发者完成接入。沉淀经验。\n\n这次最值得记录的技术决策？",
    ),
    (
        "user",
        "Key验证的三层缓存方案很实用，解决了安全和性能的矛盾。还有一个坑：bcrypt在热路径上太慢了，一开始没想到。",
    ),
    (
        "assistant",
        "提炼经验卡片：\n\n**API Key鉴权的性能与安全平衡**\n- 核心方案：三层缓存（本地10s+Redis60s+DB）\n- 关键坑：bcrypt不适合热路径，首次验证后改用SHA256缓存索引\n- 吊销：三层同步清除，最坏10s延迟\n\n确认归档？",
    ),
    ("user", "确认。"),
]

# ═══════════════════════════════════════════════════════════════
# Todo3: API调用计费系统 (v2.0, done)
# ═══════════════════════════════════════════════════════════════

T3_REQ = {
    "background": "开放平台需要商业化变现，按API调用量向开发者收费。当前所有API免费使用，缺乏商业模式。需要实现灵活的计费体系，支持阶梯定价和月度账单。",
    "user_scenarios": "1. 管理员在后台配置计费规则（按API分组定价）\n2. 开发者在控制台查看实时用量和预估费用\n3. 每月1号系统自动生成上月账单\n4. 开发者查看账单明细、下载PDF发票\n5. 余额不足时发送预警通知，欠费超期自动限流",
    "goals": "- 支持阶梯定价：前1万次免费，1万-100万每次0.001元，100万以上0.0005元\n- 计费精度：每次API调用精确计量\n- 账单生成延迟<1小时（每月1号）\n- 实时余额和用量查询\n- 支持预付费和后付费两种模式",
    "boundaries": "- 不对接真实支付系统（使用余额充值模拟）\n- 不做发票开具（仅PDF账单）\n- 不做多币种支持（仅人民币）\n- 欠费宽限期3天",
    "acceptance_criteria": "1. 每次API调用准确计入用量\n2. 阶梯定价计算正确\n3. 月度账单1号凌晨自动生成\n4. 余额低于阈值自动邮件提醒\n5. 欠费3天后自动限流到10 QPS\n6. 账单PDF可下载",
    "risk_assessment": "- 计量丢失：Kafka至少一次语义+幂等消费\n- 计费精度：使用decimal类型避免浮点误差\n- 账单生成失败：重试机制+人工补单入口",
}

T3_UI = {
    "flow_diagram": "graph TD\n    A[API调用发生] --> B[网关记录计量事件]\n    B --> C[Kafka消息队列]\n    C --> D[计费消费者]\n    D --> E[累加用量计数器]\n    E --> F{月末结算}\n    F -->|每月1号| G[计算阶梯费用]\n    G --> H[生成账单]\n    H --> I[发送账单通知]\n    E --> J{余额检查}\n    J -->|低于阈值| K[发送预警邮件]\n    J -->|欠费>3天| L[自动限流]\n    I --> M[开发者查看账单]\n    M --> N[下载PDF]",
    "wireframes": [
        {
            "page_name": "开发者计费中心",
            "description": "展示当月用量、费用预估和历史账单",
            "html": '<div class="min-h-screen bg-gray-900 p-6"><div class="max-w-4xl mx-auto"><h1 class="text-xl font-bold text-white mb-6">计费中心</h1><div class="grid grid-cols-4 gap-4 mb-6"><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">账户余额</p><p class="text-2xl font-bold text-white mt-1">¥ 2,847.50</p></div><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">本月用量</p><p class="text-2xl font-bold text-white mt-1">523,847</p><p class="text-xs text-gray-400 mt-1">次API调用</p></div><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">本月预估费用</p><p class="text-2xl font-bold text-yellow-400 mt-1">¥ 311.92</p></div><div class="bg-gray-800 rounded-lg p-4"><p class="text-xs text-gray-500">计费套餐</p><p class="text-lg font-bold text-indigo-400 mt-1">按量付费</p></div></div><div class="bg-gray-800 rounded-lg p-5 mb-4"><h2 class="text-sm font-medium text-gray-400 mb-3">阶梯定价</h2><div class="overflow-x-auto"><table class="w-full text-left text-xs"><thead><tr class="border-b border-gray-700 text-gray-500"><th class="pb-2 pr-4">区间</th><th class="pb-2 pr-4">单价</th><th class="pb-2">本月用量</th></tr></thead><tbody class="text-gray-300"><tr class="border-b border-gray-800"><td class="py-2 pr-4">0 - 10,000</td><td class="py-2 pr-4 text-green-400">免费</td><td class="py-2">10,000</td></tr><tr class="border-b border-gray-800"><td class="py-2 pr-4">10,001 - 1,000,000</td><td class="py-2 pr-4">¥0.001/次</td><td class="py-2">513,847</td></tr><tr><td class="py-2 pr-4">1,000,001+</td><td class="py-2 pr-4">¥0.0005/次</td><td class="py-2">0</td></tr></tbody></table></div></div><div class="bg-gray-800 rounded-lg p-5"><h2 class="text-sm font-medium text-gray-400 mb-3">历史账单</h2><table class="w-full text-left text-sm"><thead><tr class="border-b border-gray-700 text-xs text-gray-500"><th class="pb-2">月份</th><th class="pb-2">调用量</th><th class="pb-2">费用</th><th class="pb-2">状态</th><th class="pb-2">操作</th></tr></thead><tbody class="text-gray-300"><tr class="border-b border-gray-800"><td class="py-2">2026-04</td><td class="py-2">487,231</td><td class="py-2">¥477.23</td><td class="py-2"><span class="text-green-400 text-xs">已付</span></td><td class="py-2"><button class="text-indigo-400 text-xs">PDF</button></td></tr><tr><td class="py-2">2026-03</td><td class="py-2">312,456</td><td class="py-2">¥302.46</td><td class="py-2"><span class="text-green-400 text-xs">已付</span></td><td class="py-2"><button class="text-indigo-400 text-xs">PDF</button></td></tr></tbody></table></div></div></div>',
        },
    ],
    "component_specs": [
        {
            "name": "BalanceCard",
            "purpose": "账户余额展示",
            "behavior": "实时更新余额和预估费用",
            "states": "normal / low-balance(yellow) / overdue(red)",
        },
        {
            "name": "PricingTierTable",
            "purpose": "阶梯定价展示",
            "behavior": "高亮当前所在区间",
            "states": "loaded",
        },
        {
            "name": "BillHistoryTable",
            "purpose": "历史账单列表",
            "behavior": "支持PDF下载和明细查看",
            "states": "loading / loaded / empty",
        },
        {
            "name": "UsageTrendChart",
            "purpose": "用量趋势图",
            "behavior": "按天展示调用量和费用曲线",
            "states": "loading / loaded",
        },
    ],
    "interaction_rules": "1. 余额低于100元时卡片变黄色预警\n2. 欠费时顶部显示红色横幅提醒\n3. PDF账单在新标签页打开\n4. 用量数据每5分钟自动刷新",
    "responsive_notes": "桌面端优先，最小1024px。定价表和账单表横向滚动。",
}

T3_ARCH = {
    "architecture_overview": "基于事件驱动的API调用计费系统，精确计量+阶梯定价+自动账单。\n\n四层架构：\n1. 计量层 — 网关侧事件采集\n   - 每次API调用生成计量事件：{app_id, api_path, timestamp, status}\n   - 写入Kafka topic: api_metering\n   - 至少一次语义保证不丢\n\n2. 计费引擎 — 用量聚合+费用计算\n   - Kafka消费者：幂等累加Redis计数器\n   - 阶梯定价公式：分段累进计算\n   - decimal精度：避免浮点误差\n\n3. 账单系统 — 月度结算+PDF生成\n   - Cron Job：每月1号01:00触发\n   - 读取当月Redis用量快照 → 计算费用 → 写入bills表\n   - PDF生成：Go模板+wkhtmltopdf\n\n4. 风控层 — 余额监控+欠费处理\n   - 余额检查每小时一次\n   - 低于阈值发邮件\n   - 欠费>3天下发限流规则（10 QPS）",
    "data_model": "billing_plans 表:\n  - id: UUID, name: VARCHAR, tiers: JSONB\n  - [{from: 0, to: 10000, price: 0}, {from: 10001, to: 1000000, price: 0.001}]\n\nbalances 表:\n  - app_id: UUID PK, amount: DECIMAL(12,4)\n  - last_charged_at: TIMESTAMPTZ\n\nbills 表:\n  - id: UUID, app_id: UUID, billing_month: DATE\n  - call_count: BIGINT, amount: DECIMAL(12,4)\n  - status: ENUM(pending/paid/overdue), pdf_url: TEXT\n\nmetering_daily 表 (预聚合):\n  - app_id: UUID, date: DATE, api_path: VARCHAR\n  - call_count: BIGINT, billable_count: BIGINT",
    "api_design": "GET /api/billing/balance — 当前余额和本月预估\nGET /api/billing/usage — 本月用量明细\nGET /api/billing/bills — 历史账单列表\nGET /api/billing/bills/:id/pdf — 下载PDF账单\nPOST /api/billing/recharge — 余额充值（模拟）\nPOST /api/admin/billing/plans — 管理员配置计费方案",
    "tech_decisions": [
        {
            "decision": "计量传输方式",
            "chosen": "Kafka异步而非同步写DB",
            "reason": "API调用热路径不能被计费拖慢，Kafka解耦后网关无额外延迟",
        },
        {
            "decision": "费用计算精度",
            "chosen": "decimal(12,4)而非float",
            "reason": "金融计算必须用定点数，float累积误差在大量调用后会产生分级差异",
        },
        {
            "decision": "账单PDF方案",
            "chosen": "Go模板+wkhtmltopdf而非前端生成",
            "reason": "服务端生成保证格式一致，不依赖前端环境",
        },
    ],
    "implementation_plan": "Phase 1: 计量采集 (2天)\n  - 网关中间件发送Kafka事件\n  - 消费者幂等累加Redis计数器\n\nPhase 2: 计费引擎 (2天)\n  - 阶梯定价计算\n  - 每日预聚合任务\n\nPhase 3: 账单系统 (2天)\n  - 月度结算Cron Job\n  - PDF生成+存储\n\nPhase 4: 风控+前端 (2天)\n  - 余额监控+欠费限流\n  - 开发者计费中心页面",
}

T3_DEV = {
    "execution_log": "$ go test ./internal/billing/ -v -count=1\n=== RUN   TestTieredPricing_Free\n--- PASS: (0.00s)\n=== RUN   TestTieredPricing_SingleTier\n--- PASS: (0.00s)\n=== RUN   TestTieredPricing_CrossTier\n--- PASS: (0.00s)\n=== RUN   TestTieredPricing_LargeVolume\n--- PASS: (0.00s)\n=== RUN   TestMeteringConsumer_Idempotent\n--- PASS: (0.52s)\n=== RUN   TestBillGeneration\n--- PASS: (1.03s)\n=== RUN   TestOverdueThrottling\n--- PASS: (0.02s)\nPASS\nok  gateway/internal/billing 1.62s\n\n$ go test ./internal/billing/pdf/ -v\n=== RUN   TestPdfGeneration\n--- PASS: (2.31s)\n\n$ go build -o bin/billing-worker ./cmd/billing-worker\nBuild successful",
    "code_changes": [
        "internal/billing/tiered_pricing.go — 阶梯定价算法（decimal精度）",
        "internal/billing/metering_consumer.go — Kafka计量消费者+幂等处理",
        "internal/billing/bill_generator.go — 月度账单生成+Cron调度",
        "internal/billing/pdf/template.go — PDF账单模板",
        "internal/billing/balance_monitor.go — 余额监控+欠费限流触发",
        "api/billing_handler.go — 计费相关API",
        "migrations/003_billing.sql — 计费表结构",
    ],
    "test_results": "28/28 tests passed | Line coverage: 93.1% | Branch coverage: 85.4% | Duration: 5.48s",
    "decisions_made": [
        {
            "decision": "Redis计数器用INCRBY而非INCR循环",
            "reason": "批量消费时一次INCRBY减少Redis往返",
        },
        {
            "decision": "PDF用wkhtmltopdf而非Go原生PDF库",
            "reason": "HTML模板开发效率高，样式灵活，维护成本低",
        },
        {
            "decision": "欠费限流复用已有限流基础设施",
            "reason": "不新建限流逻辑，只需向限流配置中心下发规则",
        },
    ],
}

T3_TEST = {
    "criteria_verification": [
        {
            "criteria": "每次API调用准确计入用量",
            "status": "pass",
            "evidence": "发送10000次请求，计量消费者最终计数精确等于10000",
        },
        {
            "criteria": "阶梯定价计算正确",
            "status": "pass",
            "evidence": "523847次调用计费：免费10000+513847×0.001=¥513.85，与系统计算结果一致",
        },
        {
            "criteria": "月度账单自动生成",
            "status": "pass",
            "evidence": "模拟月末触发，账单在42秒内生成完毕",
        },
        {
            "criteria": "余额预警通知",
            "status": "pass",
            "evidence": "设置阈值100元，余额降至98元时收到邮件通知",
        },
        {
            "criteria": "欠费3天自动限流",
            "status": "pass",
            "evidence": "模拟欠费72小时后，限流规则自动下发为10 QPS",
        },
        {
            "criteria": "PDF账单可下载",
            "status": "pass",
            "evidence": "生成的PDF包含完整账单信息，格式正确",
        },
    ],
    "issues_found": [
        {
            "description": "Kafka消费者重启时可能重复计量",
            "severity": "medium",
            "suggestion": "已通过消息ID幂等去重解决，Redis SETNX检查消息是否已处理",
        },
        {
            "description": "跨月边界的API调用归属不准确",
            "severity": "low",
            "suggestion": "以Kafka消息时间戳为准，而非消费时间",
        },
    ],
    "coverage_summary": "总计 28 个测试用例，全部通过\n- 阶梯定价算法测试: 8/8 passed\n- 计量消费者测试: 6/6 passed\n- 账单生成测试: 6/6 passed\n- 余额监控测试: 4/4 passed\n- PDF生成测试: 2/2 passed\n- E2E测试: 2/2 passed\n\n代码覆盖率: Line 93.1% | Branch 85.4%\n执行耗时: 51 秒",
}

T3_DEPLOY = {
    "service_url": "https://developer.openapi.example.com/billing",
    "health_check_result": "All checks passed — Billing service healthy, Kafka consumer lag: 0, PDF generator ready",
    "deploy_log": "$ alembic upgrade head\n[OK] Migration: 003_billing — 创建 billing_plans + balances + bills 表\n\n$ docker build -t billing-worker:v2.0.0 .\n[OK] Image built: billing-worker:v2.0.0 (52MB)\n\n$ kubectl apply -f deploy/k8s/billing/\n[OK] Deployment/billing-worker: 2 replicas ready\n[OK] CronJob/bill-generator: scheduled for 01:00 monthly\n[OK] CronJob/balance-monitor: scheduled hourly\n\n$ kubectl logs deployment/billing-worker --tail=5\nINFO  Kafka consumer connected, topic=api_metering\nINFO  Metering consumer started, partition=0\nINFO  Processing rate: 1247 events/sec\n\n冒烟测试: 计量 ✓ | 阶梯计费 ✓ | 账单生成 ✓ | PDF下载 ✓ | 余额预警 ✓",
    "rollback_plan": '1. kubectl rollout undo deployment/billing-worker\n2. CronJob暂停：kubectl patch cronjob bill-generator -p \'{"spec":{"suspend":true}}\'\n3. 数据库：已生成账单保留不删，回滚只影响新计量\n4. 计量消息在Kafka中保留7天，重新消费可恢复\n\n已通知财务团队首月账单预计5月2日可查看。',
}

T3_EXP = {
    "problem": "API调用计费系统中，阶梯定价的分段累进计算在跨月边界时存在精度问题：月末最后一批调用可能被Kafka延迟到下月消费，导致费用计算错误。",
    "solution": "以Kafka消息中的事件时间戳（event_time）为准进行月份归属判断，而非消费时间。计费消费者维护两个月份的计数器（当月+上月），上月计数器在月度结算完成后才关闭。使用decimal(12,4)避免浮点累积误差。",
    "decisions": [
        {
            "point": "计量时间归属",
            "chosen": "事件时间戳而非消费时间",
            "reason": "Kafka消费可能延迟秒级到分钟级，跨月边界用消费时间会导致计费错位",
        },
        {
            "point": "计费精度",
            "chosen": "decimal(12,4)全链路",
            "reason": "100万次×0.001元=1000元，float64累积误差约0.01元，对账无法通过",
        },
    ],
    "pitfalls": [
        {
            "issue": "float浮点误差导致账单金额与手算不一致",
            "cause": "Go float64在大量累加后精度丢失",
            "fix": "全链路使用shopspring/decimal库，DB用DECIMAL类型",
        },
        {
            "issue": "Kafka消费者重启导致重复计量",
            "cause": "offset提交失败后重新消费已处理消息",
            "fix": "消息ID幂等检查：Redis SETNX(msg_id, 1, TTL=48h)",
        },
    ],
    "applicable_scenarios": "任何按量计费的SaaS平台。核心原则：事件时间为准、定点数精度、幂等消费。",
    "tags": ["计费", "Kafka", "精度", "幂等"],
}

T3_CLAR_MSGS = [
    (
        "assistant",
        "你好！来梳理「API调用计费系统」的需求。\n\n为什么现在要做计费？是商业化的要求还是成本控制？",
    ),
    (
        "user",
        "商业化。开放平台需要有收入模型，按API调用量收费是最自然的方式。现在所有API免费，没法持续。",
    ),
    (
        "assistant",
        "明白。定价模式倾向哪种？\n- 固定套餐（月包）\n- 按量计费（阶梯定价）\n- 混合模式（基础包+超出部分按量）",
    ),
    (
        "user",
        "先做按量计费，阶梯定价。前1万次免费吸引开发者，超过后按量收费。1万到100万每次0.001元，100万以上0.0005元。",
    ),
    (
        "assistant",
        "阶梯定价清晰。几个补充问题：\n1. 结算周期？按月还是按天？\n2. 预付费还是后付费？\n3. 欠费怎么处理？",
    ),
    (
        "user",
        "按月结算。支持两种：预付费充值和后付费月结。欠费给3天宽限期，超过就限流到10 QPS逼他们充值。",
    ),
    (
        "assistant",
        "需求确认：\n- 阶梯定价，按月结算\n- 支持预付费+后付费\n- 欠费3天宽限期后限流\n- 余额不足邮件预警\n- PDF账单下载\n\n确认？",
    ),
    ("user", "确认。"),
]

T3_UI_MSGS = [
    ("assistant", "开始设计计费中心的交互方案。核心信息是什么？"),
    (
        "user",
        "开发者最关心的是：我花了多少钱、这个月用了多少、余额还够不够。所以页面首屏要突出这三个数字。",
    ),
    (
        "assistant",
        "方案：\n\n**计费中心首页**\n- 四张指标卡：余额、本月用量、预估费用、当前套餐\n- 阶梯定价表：高亮当前所在区间\n- 历史账单列表：支持PDF下载\n\n余额不足时卡片变黄色，欠费时全页顶部红色横幅。\n\n线框图已生成。",
    ),
    ("user", "可以，清晰直观。"),
]

T3_ARCH_MSGS = [
    ("assistant", "进入架构设计。核心挑战：如何在不影响API性能的前提下精确计量？"),
    ("user", "计量不能拖慢API响应，必须异步。但也不能丢数据，丢了就少收钱。"),
    (
        "assistant",
        "方案：事件驱动异步计量\n\n1. 网关中间件：API响应后异步发Kafka消息（不阻塞响应）\n2. 计费消费者：从Kafka消费+幂等累加Redis计数器\n3. 月度结算：Cron触发，读Redis快照计算费用\n\n精度保障：\n- Kafka至少一次语义 + 消费者幂等去重\n- 费用计算用decimal(12,4)，不用float\n- 跨月边界用事件时间戳归属\n\n确认？",
    ),
    ("user", "确认。幂等去重具体怎么做？"),
    (
        "assistant",
        "每条Kafka消息携带唯一msg_id（网关生成的UUID）。消费者处理前先SETNX到Redis：\n- 如果SET成功：首次处理，执行计量\n- 如果SET失败：重复消息，跳过\n- TTL设48小时，覆盖Kafka最大重试窗口\n\n这样即使消费者重启导致重新消费，也不会重复计量。",
    ),
]

T3_EXT_MSGS = [
    ("assistant", "计费系统上线运行一个月，账单准确无误。沉淀经验。\n\n最值得记录的？"),
    (
        "user",
        "两个：一是float精度问题比想象中严重，100万次调用后误差有好几分钱；二是Kafka跨月边界的归属问题，用消费时间会出错。",
    ),
    (
        "assistant",
        "经验卡片：\n\n**API计费精度保障**\n- float累积误差：100万次后偏差约0.01元，必须用decimal\n- 跨月归属：以事件时间戳为准，非消费时间\n- 幂等保障：msg_id + Redis SETNX去重\n\n确认归档？",
    ),
    ("user", "确认。"),
]

# ═══════════════════════════════════════════════════════════════
# Todo4: 实时监控看板 (v2.0, done)
# ═══════════════════════════════════════════════════════════════

T4_REQ = {
    "background": "开放平台的API运行状态缺乏可视化监控，出现故障时依赖开发者报告才能发现。SRE团队需要实时看板监控全平台API健康度，提前发现异常。",
    "user_scenarios": "1. SRE打开监控大屏，一览全平台API健康状态\n2. 看板显示实时QPS、错误率、延迟分布（P50/P95/P99）\n3. 某API错误率突增时，看板红色告警+声音提醒\n4. 点击异常API查看详细指标和最近错误日志\n5. 开发者在自己的控制台查看应用级别的监控",
    "goals": "- 数据延迟<5秒（准实时）\n- 支持全平台和应用级两个视角\n- 告警规则：错误率>5%或P99>2秒\n- 历史数据回溯7天\n- 大屏模式支持投影到监控电视",
    "boundaries": "- 不做APM级别的链路追踪（用Jaeger补充）\n- 不做日志全文检索（用ELK补充）\n- 告警仅看板内推送，不对接PagerDuty\n- 不做自定义指标（固定指标集）",
    "acceptance_criteria": "1. 看板数据延迟<5秒\n2. QPS/错误率/延迟三个核心指标实时展示\n3. 异常时红色高亮+声音告警\n4. 历史数据支持7天回溯\n5. 大屏模式隐藏导航栏，全屏展示",
    "risk_assessment": "- 高频数据推送导致浏览器卡顿：降采样+requestAnimationFrame\n- WebSocket断连：自动重连+断线期间数据补偿\n- Prometheus查询慢：预聚合recording rules",
}

T4_UI = {
    "flow_diagram": "graph TD\n    A[网关请求日志] --> B[Prometheus采集]\n    B --> C[Recording Rules预聚合]\n    C --> D[Grafana/自研看板]\n    D --> E{视图选择}\n    E -->|全平台| F[平台总览大屏]\n    E -->|应用级| G[应用监控详情]\n    F --> H[QPS曲线]\n    F --> I[错误率热力图]\n    F --> J[延迟分布]\n    F --> K{告警检测}\n    K -->|异常| L[红色高亮+声音]\n    K -->|正常| M[绿色状态]\n    G --> N[应用专属指标]\n    G --> O[错误日志列表]",
    "wireframes": [
        {
            "page_name": "平台监控大屏",
            "description": "全平台API健康状态实时监控",
            "html": '<div class="min-h-screen bg-gray-950 p-4"><div class="flex items-center justify-between mb-4"><h1 class="text-lg font-bold text-white">API 平台监控</h1><div class="flex items-center gap-3"><span class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs">全部正常</span><span class="text-xs text-gray-500">更新于 2秒前</span><button class="px-3 py-1 bg-gray-800 text-gray-300 rounded text-xs">全屏</button></div></div><div class="grid grid-cols-5 gap-3 mb-4"><div class="bg-gray-900 rounded-lg p-3 text-center"><p class="text-xs text-gray-500">总QPS</p><p class="text-xl font-bold text-white">12,847</p></div><div class="bg-gray-900 rounded-lg p-3 text-center"><p class="text-xs text-gray-500">成功率</p><p class="text-xl font-bold text-green-400">99.82%</p></div><div class="bg-gray-900 rounded-lg p-3 text-center"><p class="text-xs text-gray-500">P50延迟</p><p class="text-xl font-bold text-white">12ms</p></div><div class="bg-gray-900 rounded-lg p-3 text-center"><p class="text-xs text-gray-500">P95延迟</p><p class="text-xl font-bold text-white">45ms</p></div><div class="bg-gray-900 rounded-lg p-3 text-center"><p class="text-xs text-gray-500">P99延迟</p><p class="text-xl font-bold text-yellow-400">128ms</p></div></div><div class="grid grid-cols-2 gap-3 mb-4"><div class="bg-gray-900 rounded-lg p-4"><h3 class="text-xs text-gray-500 mb-2">QPS 趋势 (最近1小时)</h3><div class="h-32 flex items-end gap-px"><div class="bg-indigo-500/60 flex-1 rounded-t" style="height:60%"></div><div class="bg-indigo-500/60 flex-1 rounded-t" style="height:72%"></div><div class="bg-indigo-500/60 flex-1 rounded-t" style="height:68%"></div><div class="bg-indigo-500/60 flex-1 rounded-t" style="height:85%"></div><div class="bg-indigo-500/60 flex-1 rounded-t" style="height:90%"></div><div class="bg-indigo-500 flex-1 rounded-t" style="height:78%"></div></div></div><div class="bg-gray-900 rounded-lg p-4"><h3 class="text-xs text-gray-500 mb-2">错误率 (最近1小时)</h3><div class="h-32 flex items-end gap-px"><div class="bg-green-500/60 flex-1 rounded-t" style="height:3%"></div><div class="bg-green-500/60 flex-1 rounded-t" style="height:2%"></div><div class="bg-green-500/60 flex-1 rounded-t" style="height:4%"></div><div class="bg-green-500/60 flex-1 rounded-t" style="height:2%"></div><div class="bg-green-500/60 flex-1 rounded-t" style="height:1%"></div><div class="bg-green-500 flex-1 rounded-t" style="height:2%"></div></div></div></div><div class="bg-gray-900 rounded-lg p-4"><h3 class="text-xs text-gray-500 mb-3">API 健康状态</h3><table class="w-full text-left text-xs"><thead><tr class="border-b border-gray-800 text-gray-500"><th class="pb-2">API</th><th class="pb-2">QPS</th><th class="pb-2">错误率</th><th class="pb-2">P99</th><th class="pb-2">状态</th></tr></thead><tbody class="text-gray-300"><tr class="border-b border-gray-800/50"><td class="py-2">/v1/users/query</td><td class="py-2">4,231</td><td class="py-2 text-green-400">0.1%</td><td class="py-2">89ms</td><td class="py-2"><span class="w-2 h-2 bg-green-400 rounded-full inline-block"></span></td></tr><tr class="border-b border-gray-800/50"><td class="py-2">/v1/orders/create</td><td class="py-2">1,847</td><td class="py-2 text-green-400">0.3%</td><td class="py-2">156ms</td><td class="py-2"><span class="w-2 h-2 bg-green-400 rounded-full inline-block"></span></td></tr><tr><td class="py-2">/v1/products/search</td><td class="py-2">6,769</td><td class="py-2 text-green-400">0.05%</td><td class="py-2">42ms</td><td class="py-2"><span class="w-2 h-2 bg-green-400 rounded-full inline-block"></span></td></tr></tbody></table></div></div>',
        },
    ],
    "component_specs": [
        {
            "name": "MetricCard",
            "purpose": "核心指标卡片",
            "behavior": "WebSocket实时更新数值",
            "states": "normal / warning(yellow) / critical(red)",
        },
        {
            "name": "TimeSeriesChart",
            "purpose": "时序曲线图",
            "behavior": "实时追加数据点+自动滚动",
            "states": "loading / streaming / paused",
        },
        {
            "name": "ApiHealthTable",
            "purpose": "API健康状态列表",
            "behavior": "按错误率排序，异常API置顶",
            "states": "all-green / has-warnings / has-alerts",
        },
        {
            "name": "AlertBanner",
            "purpose": "告警横幅",
            "behavior": "异常时顶部红色闪烁+声音",
            "states": "hidden / active / acknowledged",
        },
    ],
    "interaction_rules": "1. 看板数据WebSocket推送，每2秒更新\n2. 异常API行变红并置顶\n3. 全屏模式隐藏导航，适配大屏投影\n4. 点击API行展开详细指标\n5. 告警声音可手动关闭（静音按钮）",
    "responsive_notes": "大屏模式优先（1920×1080），也支持笔记本（1440×900）。指标卡5列→3列自适应。",
}

T4_ARCH = {
    "architecture_overview": "基于Prometheus+WebSocket的实时监控看板系统。\n\n数据流：\n1. 采集层 — Prometheus指标\n   - 网关暴露/metrics端点\n   - Prometheus每5秒scrape\n   - Recording rules预聚合高频查询\n\n2. 推送层 — WebSocket实时下发\n   - Go服务订阅Prometheus查询结果\n   - WebSocket广播给所有连接的看板\n   - 每2秒推送一次指标快照\n\n3. 展示层 — React看板\n   - 时序图表：Recharts库\n   - requestAnimationFrame控制渲染频率\n   - 本地buffer 60秒数据做平滑\n\n4. 告警层 — 阈值检测\n   - 服务端检测异常（错误率>5% / P99>2s）\n   - WebSocket推送告警事件\n   - 看板播放告警音+红色高亮",
    "data_model": "Prometheus指标:\n  - gateway_requests_total{app_id, api_path, status} — 请求计数\n  - gateway_request_duration_seconds{app_id, api_path} — 延迟直方图\n  - gateway_circuit_breaker_state{api_path} — 熔断状态\n\nRecording Rules:\n  - gateway:qps:5s — 5秒粒度QPS\n  - gateway:error_rate:5s — 5秒粒度错误率\n  - gateway:latency_p99:5s — 5秒粒度P99\n\nalert_rules 表:\n  - id: UUID, metric: VARCHAR, threshold: FLOAT\n  - duration: INTERVAL, severity: ENUM(warning/critical)",
    "api_design": "WS /ws/monitor — 看板实时数据推送\nGET /api/monitor/snapshot — 当前指标快照\nGET /api/monitor/history?range=1h — 历史指标查询\nGET /api/monitor/alerts — 当前告警列表\nPOST /api/monitor/alerts/:id/acknowledge — 确认告警",
    "tech_decisions": [
        {
            "decision": "数据推送方式",
            "chosen": "WebSocket而非SSE",
            "reason": "看板需要双向通信（切换视图时服务端调整推送内容）",
        },
        {
            "decision": "图表库",
            "chosen": "Recharts而非ECharts",
            "reason": "React生态原生支持，bundle更小，实时更新性能更好",
        },
        {
            "decision": "告警检测位置",
            "chosen": "服务端检测而非前端",
            "reason": "服务端统一判断避免多个看板重复检测产生不一致",
        },
    ],
    "implementation_plan": "Phase 1: 指标采集 (1天)\n  - Prometheus配置+Recording Rules\n  - 网关/metrics端点\n\nPhase 2: WebSocket推送 (2天)\n  - Go WebSocket服务\n  - Prometheus查询+广播\n\nPhase 3: 看板前端 (3天)\n  - 指标卡片+时序图表\n  - API健康表格\n  - 全屏大屏模式\n\nPhase 4: 告警 (1天)\n  - 阈值检测+WebSocket告警\n  - 声音+视觉提醒",
}

T4_DEV = {
    "execution_log": "$ go test ./internal/monitor/ -v -count=1\n=== RUN   TestWebSocketBroadcast\n--- PASS: (0.12s)\n=== RUN   TestPrometheusQuery\n--- PASS: (0.08s)\n=== RUN   TestAlertDetection\n--- PASS: (0.01s)\n=== RUN   TestAlertThreshold_ErrorRate\n--- PASS: (0.01s)\n=== RUN   TestAlertThreshold_Latency\n--- PASS: (0.01s)\nPASS\nok  gateway/internal/monitor 0.28s\n\n$ cd web/monitor-dashboard && npm test\nPASS src/components/MetricCard.test.tsx\nPASS src/components/TimeSeriesChart.test.tsx\nPASS src/hooks/useWebSocket.test.ts\n12 passed in 3.41s\n\n$ npm run build\nvite v5.x building...\n✓ 78 modules transformed.\ndist/index.html  0.32 kB\ndist/assets/monitor.js  98.45 kB\n✓ built in 2.1s",
    "code_changes": [
        "internal/monitor/ws_hub.go — WebSocket连接管理+广播",
        "internal/monitor/prometheus_query.go — Prometheus指标查询封装",
        "internal/monitor/alert_detector.go — 告警阈值检测",
        "web/monitor-dashboard/src/App.tsx — 监控看板主页面",
        "web/monitor-dashboard/src/components/MetricCard.tsx — 实时指标卡片",
        "web/monitor-dashboard/src/components/TimeSeriesChart.tsx — 时序图表",
        "deploy/prometheus/recording_rules.yml — 预聚合规则",
    ],
    "test_results": "22/22 tests passed | Line coverage: 86.4% | Branch coverage: 78.9% | Duration: 3.69s",
    "decisions_made": [
        {
            "decision": "WebSocket每2秒推送而非每秒",
            "reason": "1秒推送浏览器渲染压力大，2秒是肉眼感知的平衡点",
        },
        {
            "decision": "前端用requestAnimationFrame节流渲染",
            "reason": "避免WebSocket消息频率超过屏幕刷新率导致丢帧",
        },
        {
            "decision": "Recording Rules预聚合",
            "reason": "实时查询原始指标Prometheus响应慢（>1s），预聚合后<50ms",
        },
    ],
}

T4_TEST = {
    "criteria_verification": [
        {
            "criteria": "看板数据延迟<5秒",
            "status": "pass",
            "evidence": "从API调用到看板数据更新实测延迟3.2秒",
        },
        {
            "criteria": "QPS/错误率/延迟实时展示",
            "status": "pass",
            "evidence": "三个核心指标均通过WebSocket实时更新，刷新间隔2秒",
        },
        {
            "criteria": "异常时红色高亮+声音告警",
            "status": "pass",
            "evidence": "模拟错误率升至8%，1个推送周期(2s)后卡片变红并播放告警音",
        },
        {
            "criteria": "历史数据7天回溯",
            "status": "pass",
            "evidence": "切换时间范围到7天前，Prometheus正确返回历史数据",
        },
        {
            "criteria": "大屏模式全屏展示",
            "status": "pass",
            "evidence": "全屏后导航栏隐藏，内容充满1920×1080分辨率",
        },
    ],
    "issues_found": [
        {
            "description": "50+浏览器同时连接WebSocket时推送延迟增加",
            "severity": "low",
            "suggestion": "已优化为批量序列化+并发写，50连接延迟从120ms降至15ms",
        },
        {
            "description": "时序图表在Safari上偶发渲染闪烁",
            "severity": "low",
            "suggestion": "已添加will-change CSS属性启用GPU加速",
        },
    ],
    "coverage_summary": "总计 22 个测试用例，全部通过\n- WebSocket推送测试: 6/6 passed\n- 指标查询测试: 4/4 passed\n- 告警检测测试: 4/4 passed\n- 前端组件测试: 6/6 passed\n- E2E测试: 2/2 passed\n\n代码覆盖率: Line 86.4% | Branch 78.9%\n执行耗时: 28 秒",
}

T4_DEPLOY = {
    "service_url": "https://monitor.openapi.example.com",
    "health_check_result": "All checks passed — WebSocket hub active (3 connections), Prometheus query latency 32ms, Alert detector running",
    "deploy_log": '$ kubectl apply -f deploy/prometheus/recording_rules.yml\n[OK] PrometheusRule/gateway-aggregation updated\n\n$ docker build -t monitor-dashboard:v2.0.0 .\n[OK] Image built: monitor-dashboard:v2.0.0 (38MB)\n\n$ kubectl apply -f deploy/k8s/monitor/\n[OK] Deployment/monitor-ws: 2 replicas ready\n[OK] Deployment/monitor-dashboard: 2 replicas ready\n[OK] Ingress/monitor.openapi.example.com configured\n\n$ wscat -c wss://monitor.openapi.example.com/ws/monitor\nConnected\n< {"type":"snapshot","qps":12847,"error_rate":0.18,"p99_ms":128}\n\n冒烟测试: WebSocket连接 ✓ | 实时推送 ✓ | 告警检测 ✓ | 大屏模式 ✓ | 历史回溯 ✓',
    "rollback_plan": "1. kubectl rollout undo deployment/monitor-ws\n2. kubectl rollout undo deployment/monitor-dashboard\n3. Prometheus recording rules: kubectl apply -f deploy/prometheus/recording_rules.yml.bak\n4. 看板不影响核心业务，回滚后监控暂时不可用但API正常\n\n已配置Grafana备用看板作为降级方案。",
}

T4_EXP = {
    "problem": "实时监控看板在高频WebSocket推送下浏览器出现严重卡顿：每秒推送1次指标数据，50个数据点的Recharts图表重渲染耗时>16ms导致丢帧。",
    "solution": "三层优化：1) 服务端降频到2秒推送一次（人眼感知极限）；2) 前端用requestAnimationFrame控制渲染，WebSocket消息先入buffer；3) 图表组件用React.memo+自定义shouldComponentUpdate，只在可见区域内重渲染。优化后帧率稳定60fps。",
    "decisions": [
        {
            "point": "推送频率",
            "chosen": "2秒而非1秒",
            "reason": "1秒推送在复杂图表场景下浏览器渲染跟不上，2秒是人眼感知和性能的平衡点",
        },
        {
            "point": "图表库",
            "chosen": "Recharts而非ECharts",
            "reason": "React原生、SVG渲染控制精细、bundle 40KB vs 400KB",
        },
    ],
    "pitfalls": [
        {
            "issue": "WebSocket推送频率超过浏览器渲染能力",
            "cause": "每次推送触发setState→React重渲染→Recharts重绘SVG",
            "fix": "消息入buffer+rAF节流，把N次推送合并为1次渲染",
        },
        {
            "issue": "Safari GPU渲染闪烁",
            "cause": "频繁DOM更新触发图层重组",
            "fix": "will-change: transform 提示浏览器保持GPU图层",
        },
    ],
    "applicable_scenarios": "任何高频实时数据可视化场景：监控看板、实时交易、IoT数据展示。核心原则：推送频率匹配渲染能力，数据buffer+rAF节流。",
    "tags": ["监控", "WebSocket", "实时渲染", "性能优化"],
}

T4_CLAR_MSGS = [
    ("assistant", "来梳理「实时监控看板」的需求。\n\n目前平台的可观测性怎么样？出问题怎么发现的？"),
    (
        "user",
        "基本是裸奔。有Prometheus采集指标但没有统一看板，出问题全靠开发者报告。上次API网关降级了15分钟，是用户投诉后才发现的。",
    ),
    (
        "assistant",
        "太被动了。需要主动监控+告警。\n\n核心诉求：\n1. 实时看板——一眼看全平台健康度\n2. 异常告警——错误率/延迟超标时主动通知\n\n目标用户是SRE还是开发者？",
    ),
    (
        "user",
        "两个视角都需要。SRE看全平台的，开发者看自己应用的。重点是SRE的大屏监控，要能投到办公区的电视上。",
    ),
    (
        "assistant",
        "需求确认：\n- 全平台+应用级两个视角\n- 核心指标：QPS、错误率、延迟分位值\n- 数据延迟<5秒\n- 异常自动告警（声音+视觉）\n- 支持大屏投影模式\n- 历史回溯7天\n\n确认？",
    ),
    ("user", "确认。"),
]

T4_UI_MSGS = [
    ("assistant", "设计监控看板的交互。大屏场景下最重要的是什么？"),
    (
        "user",
        "信息密度要高但不能乱。一眼能看到：总QPS、错误率、延迟，以及哪些API有问题。有问题的要非常醒目。",
    ),
    (
        "assistant",
        "方案：\n\n**大屏监控页**\n- 顶栏：平台名+全局状态灯+最后更新时间+全屏按钮\n- 第一行：5个指标卡（总QPS/成功率/P50/P95/P99）\n- 第二行：QPS趋势+错误率趋势两个时序图\n- 第三行：API健康状态表格（异常置顶+红色高亮）\n\n配色以深色为主（bg-gray-950），数据用高对比色。异常时整行变红+状态灯闪烁。\n\n线框图已生成。",
    ),
    ("user", "可以。注意大屏模式下字体要足够大，3米外能看清。"),
]

T4_ARCH_MSGS = [
    (
        "assistant",
        "架构设计。实时数据如何从Prometheus到浏览器？\n\n方案对比：\n1. 前端直接查Prometheus（简单但频繁查询压力大）\n2. 中间层汇聚+WebSocket推送（多一层但可控）",
    ),
    ("user", "WebSocket推送。不想让前端直接查Prometheus，而且WebSocket可以做告警推送。"),
    (
        "assistant",
        "方案确认：\n\n**数据流**：Prometheus → Go中间层 → WebSocket → 浏览器\n\nGo中间层职责：\n1. 定时查Prometheus（每2秒）\n2. 指标聚合+格式化\n3. WebSocket广播给所有看板\n4. 告警阈值检测\n\n前端优化：\n- requestAnimationFrame节流渲染\n- 本地buffer 60秒做图表平滑\n- React.memo防止无关组件重渲染\n\n确认？",
    ),
    ("user", "确认。"),
]

T4_EXT_MSGS = [
    ("assistant", "监控看板上线一周，SRE团队反馈很好。沉淀经验。"),
    (
        "user",
        "最大的收获是实时看板的性能优化。一开始每秒推一次数据浏览器直接卡死，降到2秒+rAF节流才稳住。",
    ),
    (
        "assistant",
        "经验卡片：\n\n**实时监控看板性能优化**\n- 核心问题：高频WebSocket推送导致浏览器丢帧\n- 方案：2秒推送+rAF节流+React.memo\n- Safari坑：频繁DOM更新需will-change提示\n\n确认归档？",
    ),
    ("user", "确认。"),
]


# ═══════════════════════════════════════════════════════════════
# Main insertion function
# ═══════════════════════════════════════════════════════════════


async def seed_gateway_project(db: AsyncSession, user_id, now: datetime) -> dict:
    """Insert 开发者开放平台 project with 3 versions, 4 full-pipeline todos + 2 pending."""

    async def _insert(table: str, values: dict) -> None:
        cols = ", ".join(f'"{k}"' if k == "order" else k for k in values.keys())
        params = ", ".join(f":{k}" for k in values.keys())
        await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)

    async def _insert_messages(conv_id, messages, base_time):
        for i, (role, content) in enumerate(messages):
            await _insert(
                "messages",
                {
                    "id": uuid.uuid4(),
                    "conversation_id": conv_id,
                    "role": role,
                    "content": content,
                    "created_at": base_time + timedelta(minutes=i * 3),
                },
            )

    # ── IDs ──
    project_id = uuid.uuid4()
    ver1_id, ver2_id, ver3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo1_id, todo2_id, todo3_id, todo4_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo5_id, todo6_id = uuid.uuid4(), uuid.uuid4()

    phases = [
        "clarification",
        "ui_design",
        "architecture",
        "development",
        "testing",
        "deployment",
        "extraction",
    ]
    conv_phases = ["clarification", "ui_design", "architecture", "extraction"]
    agent_phases = ["development", "testing", "deployment"]

    # Phase/conv/agent IDs for todos 1-4
    phase_ids = {}
    conv_ids = {}
    agent_ids = {}
    for t in [todo1_id, todo2_id, todo3_id, todo4_id]:
        phase_ids[t] = {p: uuid.uuid4() for p in phases}
        conv_ids[t] = {p: uuid.uuid4() for p in conv_phases}
        agent_ids[t] = {p: uuid.uuid4() for p in agent_phases}

    # ── Project ──
    await _insert(
        "projects",
        {
            "id": project_id,
            "user_id": user_id,
            "name": "开发者开放平台",
            "description": "面向第三方开发者的API网关平台，支持应用接入、限流熔断、计费统计和实时监控",
            "tech_stack": "Go + gRPC + Redis + Kubernetes + Prometheus",
            "status": "active",
            "created_at": now - timedelta(days=60),
            "updated_at": now,
        },
    )

    # ── Versions ──
    await _insert(
        "versions",
        {
            "id": ver1_id,
            "project_id": project_id,
            "name": "v1.0",
            "goal": "API网关基础能力：限流熔断 + 第三方应用接入",
            "status": "released",
            "order": 1,
            "created_at": now - timedelta(days=60),
            "updated_at": now - timedelta(days=20),
        },
    )
    await _insert(
        "versions",
        {
            "id": ver2_id,
            "project_id": project_id,
            "name": "v2.0",
            "goal": "计费与监控：API调用计费 + 实时监控看板",
            "status": "active",
            "order": 2,
            "created_at": now - timedelta(days=30),
            "updated_at": now,
        },
    )
    await _insert(
        "versions",
        {
            "id": ver3_id,
            "project_id": project_id,
            "name": "v3.0",
            "goal": "开放生态：开发者文档门户 + SDK自动生成",
            "status": "planning",
            "order": 3,
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    # ── Data mapping for the 4 full-pipeline todos ──
    todo_defs = [
        # (todo_id, ver_id, title, desc, tags, time_offset_days, priority)
        (
            todo1_id,
            ver1_id,
            "API限流与熔断",
            "基于令牌桶算法的API限流，支持按应用/接口粒度配置，Sentinel熔断降级",
            [{"label": "后端", "color": "#4A9FD8"}, {"label": "稳定性", "color": "#EF4444"}],
            55,
            1,
        ),
        (
            todo2_id,
            ver1_id,
            "第三方应用接入",
            "开发者注册、应用创建、API Key管理和调用统计看板",
            [{"label": "全栈", "color": "#6366F1"}, {"label": "核心功能", "color": "#F59E0B"}],
            50,
            2,
        ),
        (
            todo3_id,
            ver2_id,
            "API调用计费系统",
            "按量阶梯定价计费，支持预付费/后付费，月度自动账单和余额预警",
            [{"label": "后端", "color": "#4A9FD8"}, {"label": "商业化", "color": "#EC4899"}],
            28,
            1,
        ),
        (
            todo4_id,
            ver2_id,
            "实时监控看板",
            "基于Prometheus+WebSocket的实时API监控，支持全平台和应用级视角",
            [{"label": "全栈", "color": "#34D399"}, {"label": "可观测", "color": "#A78BFA"}],
            25,
            2,
        ),
    ]

    artifact_map = {
        todo1_id: {
            "req": T1_REQ,
            "ui": T1_UI,
            "arch": T1_ARCH,
            "dev": T1_DEV,
            "test": T1_TEST,
            "deploy": T1_DEPLOY,
            "exp": T1_EXP,
        },
        todo2_id: {
            "req": T2_REQ,
            "ui": T2_UI,
            "arch": T2_ARCH,
            "dev": T2_DEV,
            "test": T2_TEST,
            "deploy": T2_DEPLOY,
            "exp": T2_EXP,
        },
        todo3_id: {
            "req": T3_REQ,
            "ui": T3_UI,
            "arch": T3_ARCH,
            "dev": T3_DEV,
            "test": T3_TEST,
            "deploy": T3_DEPLOY,
            "exp": T3_EXP,
        },
        todo4_id: {
            "req": T4_REQ,
            "ui": T4_UI,
            "arch": T4_ARCH,
            "dev": T4_DEV,
            "test": T4_TEST,
            "deploy": T4_DEPLOY,
            "exp": T4_EXP,
        },
    }

    msg_map = {
        todo1_id: {
            "clarification": T1_CLAR_MSGS,
            "ui_design": T1_UI_MSGS,
            "architecture": T1_ARCH_MSGS,
            "extraction": T1_EXT_MSGS,
        },
        todo2_id: {
            "clarification": T2_CLAR_MSGS,
            "ui_design": T2_UI_MSGS,
            "architecture": T2_ARCH_MSGS,
            "extraction": T2_EXT_MSGS,
        },
        todo3_id: {
            "clarification": T3_CLAR_MSGS,
            "ui_design": T3_UI_MSGS,
            "architecture": T3_ARCH_MSGS,
            "extraction": T3_EXT_MSGS,
        },
        todo4_id: {
            "clarification": T4_CLAR_MSGS,
            "ui_design": T4_UI_MSGS,
            "architecture": T4_ARCH_MSGS,
            "extraction": T4_EXT_MSGS,
        },
    }

    # ── Insert todos ──
    for tid, vid, title, desc, tags, offset, priority in todo_defs:
        await _insert(
            "todos",
            {
                "id": tid,
                "user_id": user_id,
                "project_id": project_id,
                "version_id": vid,
                "title": title,
                "description": desc,
                "status": "done",
                "priority": priority,
                "current_phase": "extraction",
                "tags": json.dumps(tags),
                "created_at": now - timedelta(days=offset),
                "updated_at": now - timedelta(days=offset - 14),
            },
        )

    # ── Insert conversations ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        for purpose, cid in conv_ids[tid].items():
            await _insert(
                "conversations",
                {
                    "id": cid,
                    "todo_id": tid,
                    "purpose": purpose,
                    "created_at": now - timedelta(days=offset),
                    "updated_at": now - timedelta(days=offset - 10),
                },
            )

    # ── Insert pipeline phases (without agent_session_id first) ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        for pt in phases:
            cid = conv_ids[tid].get(pt)
            await _insert(
                "pipeline_phases",
                {
                    "id": phase_ids[tid][pt],
                    "todo_id": tid,
                    "phase_type": pt,
                    "status": "confirmed",
                    "conversation_id": cid,
                    "created_at": now - timedelta(days=offset),
                    "updated_at": now - timedelta(days=offset - 12),
                },
            )

    # ── Insert agent sessions ──
    agent_configs = {
        "development": ("openhands", "completed"),
        "testing": ("openhands", "completed"),
        "deployment": ("openhands", "completed"),
    }

    task_contexts = {
        todo1_id: {
            "development": {
                "task": "实现Go令牌桶限流+熔断中间件，Redis Lua脚本原子操作，配置热更新",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "限流和熔断的集成测试和压力测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "K8s部署网关限流服务，配置HPA和Prometheus监控",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo2_id: {
            "development": {
                "task": "实现开发者注册、应用管理、API Key鉴权和调用统计",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "应用接入全流程测试、Key验证性能测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署开发者控制台和统计聚合服务",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo3_id: {
            "development": {
                "task": "实现Kafka计量消费、阶梯定价、账单生成和PDF导出",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "计费精度测试、跨月边界测试、幂等性测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署计费服务和CronJob，配置Kafka consumer group",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo4_id: {
            "development": {
                "task": "实现Prometheus查询服务、WebSocket推送和React监控看板",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "WebSocket推送性能测试、告警检测测试、大屏兼容性测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署监控看板和WebSocket服务，配置Prometheus recording rules",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
    }

    result_summaries = {
        todo1_id: {
            "development": {
                "status": "success",
                "files_changed": 7,
                "tests_added": 32,
                "lines_added": 1847,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 32,
                "tests_failed": 0,
                "coverage": "91.3%",
            },
            "deployment": {"status": "success", "services_deployed": 1, "replicas": 3},
        },
        todo2_id: {
            "development": {
                "status": "success",
                "files_changed": 9,
                "tests_added": 38,
                "lines_added": 2341,
                "lines_deleted": 12,
            },
            "testing": {
                "status": "success",
                "tests_passed": 38,
                "tests_failed": 0,
                "coverage": "87.6%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
        todo3_id: {
            "development": {
                "status": "success",
                "files_changed": 8,
                "tests_added": 28,
                "lines_added": 1956,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 28,
                "tests_failed": 0,
                "coverage": "93.1%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
        todo4_id: {
            "development": {
                "status": "success",
                "files_changed": 8,
                "tests_added": 22,
                "lines_added": 1423,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 22,
                "tests_failed": 0,
                "coverage": "86.4%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
    }

    for tid, _, _, _, _, offset, _ in todo_defs:
        for phase_name, (agent_type, status) in agent_configs.items():
            aid = agent_ids[tid][phase_name]
            day_offset = {
                "development": offset - 6,
                "testing": offset - 4,
                "deployment": offset - 2,
            }[phase_name]
            await _insert(
                "agent_sessions",
                {
                    "id": aid,
                    "todo_id": tid,
                    "phase_id": phase_ids[tid][phase_name],
                    "agent_type": agent_type,
                    "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
                    "status": status,
                    "task_context": json.dumps(task_contexts[tid][phase_name]),
                    "result_summary": json.dumps(result_summaries[tid][phase_name]),
                    "error_reason": "",
                    "started_at": now - timedelta(days=day_offset),
                    "completed_at": now - timedelta(days=day_offset, hours=-3),
                    "created_at": now - timedelta(days=day_offset),
                    "updated_at": now - timedelta(days=day_offset, hours=-3),
                },
            )

    # ── Link agent sessions to phases ──
    for tid in [todo1_id, todo2_id, todo3_id, todo4_id]:
        for phase_name in agent_phases:
            await db.execute(
                text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
                {"aid": agent_ids[tid][phase_name], "pid": phase_ids[tid][phase_name]},
            )

    # ── Insert messages ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        msgs = msg_map[tid]
        for purpose, messages in msgs.items():
            day_map = {
                "clarification": offset - 1,
                "ui_design": offset - 3,
                "architecture": offset - 5,
                "extraction": offset - 12,
            }
            await _insert_messages(
                conv_ids[tid][purpose], messages, now - timedelta(days=day_map[purpose])
            )

    # ── Insert artifacts ──
    art_type_map = [
        ("requirement_spec", "clarification", "req", 10),
        ("ui_design", "ui_design", "ui", 8),
        ("tech_architecture", "architecture", "arch", 6),
        ("dev_report", "development", "dev", 4),
        ("test_report", "testing", "test", 3),
        ("deploy_report", "deployment", "deploy", 2),
        ("experience_card", "extraction", "exp", 1),
    ]

    for tid, _, _, _, _, offset, _ in todo_defs:
        arts = artifact_map[tid]
        for art_type, phase_name, key, day_delta in art_type_map:
            conf_at = now - timedelta(days=offset - 14 + day_delta)
            await _insert(
                "artifacts",
                {
                    "id": uuid.uuid4(),
                    "todo_id": tid,
                    "phase_id": phase_ids[tid][phase_name],
                    "artifact_type": art_type,
                    "content": json.dumps(arts[key]),
                    "version": 1,
                    "is_confirmed": True,
                    "confirmed_at": conf_at,
                    "created_at": conf_at - timedelta(hours=2),
                    "updated_at": conf_at,
                },
            )

    # ── v3.0 pending todos ──
    await _insert(
        "todos",
        {
            "id": todo5_id,
            "user_id": user_id,
            "project_id": project_id,
            "version_id": ver3_id,
            "title": "开发者文档门户",
            "description": "自动化API文档生成，支持在线调试、代码示例和版本管理",
            "status": "pending",
            "priority": 1,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "前端", "color": "#34D399"}, {"label": "文档", "color": "#6366F1"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    await _insert(
        "todos",
        {
            "id": todo6_id,
            "user_id": user_id,
            "project_id": project_id,
            "version_id": ver3_id,
            "title": "SDK自动生成",
            "description": "基于OpenAPI Spec自动生成多语言SDK（Python/Java/Go），支持类型安全和自动补全",
            "status": "pending",
            "priority": 2,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "工具链", "color": "#F59E0B"}, {"label": "DX", "color": "#A78BFA"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    return {
        "project_id": project_id,
        "todo_ids": [todo1_id, todo2_id, todo3_id, todo4_id],
    }
