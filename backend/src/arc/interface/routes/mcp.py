"""MCP server endpoint (v5.6.0 T18).

MCP-over-HTTP: JSON-RPC 2.0 协议, 暴露 Arc artifact 给外部 AI 客户端 (Claude Desktop 等)。
Higress 等网关可前置做透传/限流/认证; 本 endpoint 是 Arc 原生 MCP 接口。

协议: JSON-RPC 2.0 over HTTP POST /mcp
methods: initialize | tools/list | tools/call
tools: arc_list_artifacts | arc_get_artifact | arc_update_artifact

认证: 复用 Arc JWT auth (CurrentUser 依赖)。外部客户端需带 Arc token。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from arc.application.artifact.service import ArtifactService
from arc.domain.artifact.policy import filter_editable_fields
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.interface.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()

PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 错误码
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_REQUEST = -32600
ERR_INTERNAL = -32603


class McpRequest(BaseModel):
    jsonrpc: str
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


# ── Tool 定义 ─────────────────────────────────────────────

_MCP_TOOLS: list[dict] = [
    {
        "name": "arc_list_artifacts",
        "description": "列出指定 todo 的所有 artifact (交付物)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string", "description": "Arc todo ID"},
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "arc_get_artifact",
        "description": "获取单个 artifact 的完整内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string"},
                "artifact_id": {"type": "string"},
            },
            "required": ["todo_id", "artifact_id"],
        },
    },
    {
        "name": "arc_update_artifact",
        "description": (
            "更新 artifact 内容 (部分合并)。仅可编辑字段生效 "
            "(文档类整体可改, 工程产物只读)。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string"},
                "artifact_id": {"type": "string"},
                "content": {
                    "type": "object",
                    "description": "要更新的字段 (partial 合并)",
                },
            },
            "required": ["todo_id", "artifact_id", "content"],
        },
    },
]


def _result(req_id, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _text_content(text: str, is_error: bool = False) -> dict:
    """MCP tool result: content 数组 + isError 标记。"""
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


# ── Tool handler ──────────────────────────────────────────

async def _call_tool(
    name: str, arguments: dict, db: DbSession, user: CurrentUser
) -> dict:
    if name == "arc_list_artifacts":
        repo = ArtifactRepository(db)
        artifacts = await repo.list_by_todo_id(uuid.UUID(arguments["todo_id"]))
        return _text_content(
            json.dumps(
                [
                    {
                        "id": str(a.id),
                        "artifact_type": a.artifact_type.value,
                        "version": a.version,
                        "is_confirmed": a.is_confirmed,
                    }
                    for a in artifacts
                ],
                ensure_ascii=False,
            )
        )

    if name == "arc_get_artifact":
        repo = ArtifactRepository(db)
        artifact = await repo.get_by_id(uuid.UUID(arguments["artifact_id"]))
        if not artifact or str(artifact.todo_id) != arguments["todo_id"]:
            return _text_content("Artifact not found", is_error=True)
        return _text_content(
            json.dumps(
                {
                    "id": str(artifact.id),
                    "artifact_type": artifact.artifact_type.value,
                    "content": artifact.content,
                    "version": artifact.version,
                },
                ensure_ascii=False,
                default=str,
            )
        )

    if name == "arc_update_artifact":
        svc = ArtifactService(db)
        artifact_id = uuid.UUID(arguments["artifact_id"])
        content = arguments.get("content", {})

        # 先校验可编辑字段, 不可编辑字段直接报错 (与 UI 一致)
        artifact = await ArtifactRepository(db).get_by_id(artifact_id)
        if not artifact:
            return _text_content("Artifact not found", is_error=True)
        _, rejected = filter_editable_fields(artifact.artifact_type, content.keys())
        if rejected:
            return _text_content(
                f"不可编辑字段: {', '.join(sorted(rejected))}",
                is_error=True,
            )

        updated = await svc.update_content(artifact_id, content, partial=True)
        if not updated:
            return _text_content("Artifact not found", is_error=True)
        return _text_content(
            json.dumps({"id": str(updated.id), "version": updated.version})
        )

    return _text_content(f"未知 tool: {name}", is_error=True)


# ── JSON-RPC 入口 ─────────────────────────────────────────

@router.post("")
async def mcp_endpoint(
    req: McpRequest, db: DbSession, user: CurrentUser,
):
    """MCP JSON-RPC 2.0 入口 (需 Arc JWT 认证)。"""
    if req.jsonrpc != "2.0":
        return _error(req.id, ERR_INVALID_REQUEST, "仅支持 jsonrpc 2.0")

    method = req.method
    params = req.params or {}

    try:
        if method == "initialize":
            return _result(req.id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "arc-mcp", "version": "5.6.0"},
            })

        if method == "tools/list":
            return _result(req.id, {"tools": _MCP_TOOLS})

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not tool_name:
                return _error(req.id, ERR_INVALID_REQUEST, "缺少 tool name")
            # 校验 tool 存在
            if not any(t["name"] == tool_name for t in _MCP_TOOLS):
                return _error(req.id, ERR_METHOD_NOT_FOUND, f"未知 tool: {tool_name}")
            result = await _call_tool(tool_name, arguments, db, user)
            return _result(req.id, result)

        return _error(req.id, ERR_METHOD_NOT_FOUND, f"未知 method: {method}")
    except ValueError as e:
        # UUID 解析失败等
        return _result(req.id, _text_content(f"参数错误: {e}", is_error=True))
    except Exception as e:
        logger.exception("MCP tool call failed")
        return _error(req.id, ERR_INTERNAL, f"内部错误: {e}")
