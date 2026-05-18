from __future__ import annotations

from fastapi import APIRouter

from arc.config import settings

router = APIRouter()


@router.get("")
async def get_settings():
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
        "agent_default": settings.agent_default,
        "agent_development": settings.agent_development,
        "agent_testing": settings.agent_testing,
        "agent_deployment": settings.agent_deployment,
    }
