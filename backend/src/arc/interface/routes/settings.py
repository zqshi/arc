from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from arc.application.settings.service import SettingsService
from arc.config import settings
from arc.interface.deps import CurrentUser

router = APIRouter()


class LLMSettingsUpdate(BaseModel):
    """系统设置更新 (LLM + Agent adapter)。

    运行时覆盖 settings → 持久化 .env → 失效 LLM adapter 缓存 →
    若涉 agent 字段则重建 AgentRegistry (波次2: skill 运行时配置)。
    """
    # LLM
    llm_provider: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_model: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str | None = None
    deepseek_model: str | None = None
    # Agent adapter (波次2) — 配置后 registry 重建, 立即可用
    openhands_url: str | None = None
    openhands_api_key: str | None = None
    codex_api_key: str | None = None
    codex_base_url: str | None = None
    claude_code_path: str | None = None
    claude_code_work_dir: str | None = None
    claude_code_model: str | None = None
    cursor_cli_path: str | None = None


@router.get("")
async def get_settings(user: CurrentUser):
    """Get current system settings (sensitive keys are masked)."""
    return {
        "llm_provider": settings.llm_provider,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "openai_api_key_set": bool(settings.openai_api_key),
        "anthropic_base_url": settings.anthropic_base_url,
        "anthropic_model": settings.anthropic_model,
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "deepseek_base_url": settings.deepseek_base_url,
        "deepseek_model": settings.deepseek_model,
        "deepseek_api_key_set": bool(settings.deepseek_api_key),
        "openhands_url": settings.openhands_url,
        "openhands_api_key_set": bool(settings.openhands_api_key),
        "codex_api_key_set": bool(settings.codex_api_key),
        "codex_base_url": settings.codex_base_url,
        "claude_code_path": settings.claude_code_path,
        "claude_code_model": settings.claude_code_model,
        "cursor_cli_path": settings.cursor_cli_path,
        "agent_default": settings.agent_default,
        "agent_development": settings.agent_development,
        "agent_testing": settings.agent_testing,
        "agent_deployment": settings.agent_deployment,
    }


@router.patch("")
async def update_settings(body: LLMSettingsUpdate, user: CurrentUser):
    """Update LLM settings at runtime and persist to .env file."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    service = SettingsService()
    return await service.update(updates)
