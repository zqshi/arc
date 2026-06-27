"""执行引擎辅助函数 — 从 execution_engine.py 提取的纯函数。

包含:
- _summarize_tool_input: 工具调用摘要生成
- _needs_user_input: 检测 AI 是否需要用户确认
- _map_tool_event: ToolLoopEvent → 前端 SSE dict 映射
- build_loop_config / extract_experience / collect_qualified_types / find_gate_stuck:
  execution_engine 尾部辅助查询 (v6.11 T4 迁入), 转 db 参数模块级函数,
  由 ExecutionEngine 调用 (原为实例方法, 迁出依赖 db/prompt_builder 显式传入)。
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def summarize_tool_input(tool_name: str, tool_input: dict) -> str:
    """生成工具调用的简洁摘要（用于持久化到 metadata）。"""
    match tool_name:
        case "read_file":
            return tool_input.get("path", "")
        case "write_file":
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            return f"{path} ({len(content.splitlines())} lines)"
        case "list_directory":
            return tool_input.get("path", ".")
        case "grep_search":
            return f'"{tool_input.get("pattern", "")}"'
        case "run_command":
            cmd = tool_input.get("command", "")
            return cmd[:80] + ("..." if len(cmd) > 80 else "")
        case _:
            return str(tool_input)[:60]


def needs_user_input(content: str) -> bool:
    """检测 AI 输出是否需要用户确认/澄清。"""
    if "[NEEDS_INPUT]" in content:
        return True
    last_paragraph = content.strip().split("\n\n")[-1] if content.strip() else ""
    question_indicators = ["？", "?", "你觉得", "你希望", "请确认", "你选择", "你倾向"]
    return any(ind in last_paragraph for ind in question_indicators)


def map_tool_event(event) -> list[dict]:
    """将 ToolLoopEvent 映射为前端 SSE 字典。"""
    results = []
    mid = event.metadata.get("message_id", str(uuid.uuid4()))

    if event.type == "text_delta":
        results.append({"message_id": mid, "content": event.content})
    elif event.type == "tool_call":
        results.append({
            "message_id": mid,
            "event": "tool_call",
            "tool_name": event.content,
            "tool_input": event.metadata.get("input", {}),
            "round": event.metadata.get("round", 0),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type == "tool_result":
        results.append({
            "message_id": mid,
            "event": "tool_result",
            "tool_name": event.metadata.get("tool_name", ""),
            "output_preview": event.content,
            "is_error": event.metadata.get("is_error", False),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type in ("orchestration_start", "synthesis_start", "orchestration_complete"):
        results.append({"event": event.type, **event.metadata})
    elif event.type in ("worker_start", "worker_complete", "worker_error"):
        results.append({"event": event.type, **event.metadata})
    elif event.type == "approval_required":
        results.append({"event": "approval_required", **event.metadata})
    elif event.type == "error":
        logger.error("Tool loop error: %s", event.content)
        results.append({
            "message_id": mid,
            "event": "tool_error",
            "detail": event.content,
        })
    elif event.type == "complete":
        logger.info(
            "Tool loop complete: %d rounds, %d tokens, %dms",
            event.metadata.get("tool_rounds", 0),
            event.metadata.get("total_tokens", 0),
            event.metadata.get("elapsed_ms", 0),
        )
        results.append({
            "event": "complete_metrics",
            "metrics": {
                "tool_rounds": event.metadata.get("tool_rounds", 0),
                "total_tokens": event.metadata.get("total_tokens", 0),
                "elapsed_ms": event.metadata.get("elapsed_ms", 0),
            },
        })
    return results


# ---------------------------------------------------------------------------
# ExecutionEngine 尾部辅助查询 (v6.11 T4 从 execution_engine.py 迁入)
# ---------------------------------------------------------------------------


async def trigger_pre_llm_hooks(
    hooks, conversation_id: str, message_count: int, project_path: str | None,
) -> None:
    """触发 pre_input / pre_llm 两个 Hook (Harness §12)。

    execution_engine.generate_response_stream 开头机械触发, v6.11 T4 迁入。
    """
    from arc.application.hooks.manager import HookPoint

    await hooks.trigger(HookPoint.PRE_INPUT, {
        "conversation_id": conversation_id,
        "message_count": message_count,
    })
    await hooks.trigger(HookPoint.PRE_LLM, {
        "conversation_id": conversation_id,
        "project_path": project_path,
    })


async def build_loop_config(db, todo_id: uuid.UUID):
    """构建 text-only AgentLoop 配置 (从项目 conversation_config 读取)。"""
    from arc.application.execution.agent_loop import LoopConfig
    from arc.infrastructure.repositories.project import ProjectRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    todo_repo = TodoRepository(db)
    todo = await todo_repo.get_by_id(todo_id)
    if not todo or not todo.project_id:
        return LoopConfig()

    project = await ProjectRepository(db).get_by_id(todo.project_id)
    if not project or not project.conversation_config:
        return LoopConfig()

    loop_cfg = project.conversation_config.get("loop_config", {})
    return LoopConfig(
        token_budget=loop_cfg.get("token_budget", 120000),
        wall_timeout_seconds=loop_cfg.get("wall_timeout_seconds", 300.0),
        max_tokens_per_call=loop_cfg.get("max_tokens_per_call", 16384),
    )


async def extract_experience(db, todo_id: uuid.UUID, prompt_builder) -> None:
    """从质量达标交付物提炼经验并反馈注入。"""
    from arc.application.execution.experience_feedback import extract_and_feedback

    await extract_and_feedback(db, todo_id, prompt_builder)


async def collect_qualified_types(db, todo_id: uuid.UUID) -> set[str]:
    """收集 todo 下已过质量门禁的交付物类型 (content._quality.passed=True)。"""
    from arc.infrastructure.repositories.artifact import ArtifactRepository

    try:
        arts = await ArtifactRepository(db).list_by_todo_id(todo_id)
    except Exception:
        return set()
    result: set[str] = set()
    for a in arts:
        if isinstance(a.content, dict):
            q = a.content.get("_quality")
            if isinstance(q, dict) and q.get("passed") is True:
                result.add(a.artifact_type.value)
    return result


async def find_gate_stuck(db, todo_id: uuid.UUID) -> dict | None:
    """找最该修复的未通过门禁产出物 (score 最低者优先)。"""
    from arc.domain.artifact.value_objects import ARTIFACT_LABELS
    from arc.infrastructure.repositories.artifact import ArtifactRepository

    try:
        arts = await ArtifactRepository(db).list_by_todo_id(todo_id)
    except Exception:
        return None
    stuck: list[tuple] = []
    for a in arts:
        if isinstance(a.content, dict):
            q = a.content.get("_quality")
            if isinstance(q, dict) and q.get("passed") is False:
                stuck.append((a, q))
    if not stuck:
        return None
    stuck.sort(key=lambda x: x[1].get("score", 5))
    a, q = stuck[0]
    return {
        "type": a.artifact_type.value,
        "label": ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value),
        "gaps": list(q.get("gaps", [])),
    }


async def map_agent_loop_events(event_iter) -> "object":
    """AgentLoop 事件流 → 前端 SSE dict (v6.11 T4 从 execution_engine 迁入)。

    与 map_tool_event (ToolLoopEvent→SSE) 同构, 维护 message_id 累积状态,
    yield {"message_id", "content"} 文本块 与 {"event":"complete_metrics", "metrics"} 完成事件。
    其余事件类型 (continuation/validation_retry/budget_warning/error) 仅记日志不产出。
    """
    message_id: str | None = None
    async for event in event_iter:
        if event.type == "chunk":
            if message_id is None:
                message_id = event.metadata.get("message_id", str(uuid.uuid4()))
            yield {"message_id": message_id, "content": event.content}

        elif event.type == "continuation":
            logger.info(
                "Agent loop continuation #%d",
                event.metadata.get("iteration", 0),
            )

        elif event.type == "validation_retry":
            logger.info(
                "Agent loop validation retry #%d",
                event.metadata.get("retry", 0),
            )

        elif event.type == "budget_warning":
            logger.warning(
                "Agent loop budget: %s/%s tokens",
                event.metadata.get("total_tokens"),
                event.metadata.get("budget"),
            )

        elif event.type == "error":
            logger.error("Agent loop error: %s", event.content)

        elif event.type == "complete":
            metrics = event.metadata.get("metrics", {})
            if message_id is None:
                message_id = event.metadata.get("message_id", str(uuid.uuid4()))
            logger.info(
                "Agent loop complete: %d iters, %dms, by=%s",
                metrics.get("iterations", 0),
                metrics.get("elapsed_ms", 0),
                event.metadata.get("terminated_by", "unknown"),
            )
            yield {"event": "complete_metrics", "metrics": metrics}
