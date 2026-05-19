# Coding Agent 升级计划

> 内部参考文档，记录各 Agent 适配器的当前状态和实现路线。

## 当前状态

| Agent | 状态 | 适配器文件 | 说明 |
|-------|------|-----------|------|
| OpenHands | **已实现** | `adapters/openhands.py` | 完整实现，含 session 创建/轮询/事件获取/取消 |
| Claude Code | 骨架 | `adapters/claude_code.py` | `implemented=False`，全部方法 raise NotImplementedError |
| Codex | 骨架 | `adapters/codex.py` | `implemented=False`，全部方法 raise NotImplementedError |
| Cursor | 骨架 | `adapters/cursor.py` | `implemented=False`，全部方法 raise NotImplementedError |

注册机制：`registry.py` 中 `create_agent_registry()` 仅注册 `implemented=True` 的适配器，骨架适配器不会被注册到运行时。

## 架构说明

```
CodingAgentAdapter (ABC)
├── start(context) → session_id
├── get_status(session_id) → SessionStatus
├── get_events(session_id, since) → list[AgentEvent]
├── cancel(session_id) → None
└── close() → None

AgentRegistry
├── register(agent_type, factory)
├── create(agent_type) → CodingAgentAdapter
├── available_agents() → list[AgentType]
└── is_available(agent_type) → bool
```

任何新 Agent 只需实现 `CodingAgentAdapter` 接口并在 `create_agent_registry()` 中注册即可。

## 升级优先级

### P0 — Claude Code 适配器

**理由**: Claude Code 的 CLI（`claude`）已发布稳定版，支持 `--print` / `--json` 模式，可以通过 subprocess 直接集成。

**实现路线**:
1. 通过 `asyncio.create_subprocess_exec` 启动 `claude` CLI
2. 使用 `--json` 模式获取结构化输出
3. 解析 stdout 为 AgentEvent 流
4. 通过 SIGTERM 实现取消
5. 工作目录由 `settings.claude_code_work_dir` 控制

**预计工作量**: 2-3 天

**依赖**: 目标机器需安装 Claude Code CLI

### P1 — Codex 适配器

**理由**: OpenAI Codex CLI 暴露了 OpenAI 兼容 API，可复用 OpenAI SDK。

**实现路线**:
1. 使用 `openai` SDK，配置自定义 `base_url`
2. Task 提交通过 API 调用
3. 轮询 task 状态
4. 事件获取复用 OpenAI 的 response 结构

**预计工作量**: 1-2 天

**依赖**: `codex_api_key` + `codex_base_url` 配置

### P2 — Cursor 适配器

**理由**: Cursor 的 CLI 接口尚不稳定，需要等待其 API 正式发布后再集成。

**实现路线**:
1. 等待 Cursor 发布稳定的 CLI 或 API
2. 参照 Claude Code 的 subprocess 模式实现
3. 或通过 Cursor 的 Extensions API 对接

**预计工作量**: 待定（依赖 Cursor 官方 API 稳定性）

## 后台任务限制

当前 Agent 会话执行通过 `asyncio.create_task` 在后台运行。已知限制：

1. **进程重启丢失运行中任务** — 通过 `_cleanup_orphan_agent_sessions` 在启动时标记为 error
2. **无持久化任务队列** — 适用于单实例部署，多实例需引入 Celery/ARQ
3. **最大执行时长 30 分钟** — 超时自动取消
4. **轮询间隔 5 秒** — 在高并发场景可能产生 API 速率压力

**后续演进方向**: 引入 ARQ（基于 Redis）作为持久化任务队列，实现：
- 任务在进程重启后自动恢复
- 多 worker 横向扩展
- 优先级队列（开发 > 测试 > 部署）
