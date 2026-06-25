from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from arc.config import settings
from arc.interface.deps import CurrentUser

router = APIRouter()


class LLMSettingsUpdate(BaseModel):
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
        "agent_default": settings.agent_default,
        "agent_development": settings.agent_development,
        "agent_testing": settings.agent_testing,
        "agent_deployment": settings.agent_deployment,
    }


@router.patch("")
async def update_settings(body: LLMSettingsUpdate, user: CurrentUser):
    """Update LLM settings at runtime and persist to .env file."""
    import os
    from pathlib import Path

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    # 运行时覆盖 settings 对象
    for key, value in updates.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)

    # 持久化到 .env 文件
    env_path = Path(os.environ.get("ENV_FILE", ".env"))
    if not env_path.exists():
        # 尝试后端根目录
        backend_env = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
        if backend_env.exists():
            env_path = backend_env

    _persist_to_env(env_path, updates)

    # 清除 adapter 缓存让下次请求使用新配置
    try:
        from arc.application.ai.adapter_pool import adapter_pool
        await adapter_pool.shutdown()
    except Exception:
        pass

    return {
        "status": "updated",
        "llm_provider": settings.llm_provider,
        "updated_fields": list(updates.keys()),
    }


def _persist_to_env(env_path, updates: dict) -> None:
    """将更新的配置写入 .env 文件。"""

    # 环境变量名映射
    key_map = {
        "llm_provider": "LLM_PROVIDER",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_base_url": "OPENAI_BASE_URL",
        "openai_model": "OPENAI_MODEL",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "anthropic_base_url": "ANTHROPIC_BASE_URL",
        "anthropic_model": "ANTHROPIC_MODEL",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "deepseek_base_url": "DEEPSEEK_BASE_URL",
        "deepseek_model": "DEEPSEEK_MODEL",
    }

    try:
        lines = env_path.read_text().splitlines() if env_path.exists() else []
    except Exception:
        lines = []

    existing_keys = {}
    for i, line in enumerate(lines):
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            existing_keys[k] = i

    for field, value in updates.items():
        if value is None:
            continue
        env_key = key_map.get(field, field.upper())
        if env_key in existing_keys:
            lines[existing_keys[env_key]] = f"{env_key}={value}"
        else:
            lines.append(f"{env_key}={value}")

    try:
        env_path.write_text("\n".join(lines) + "\n")
    except Exception:
        pass  # 写入失败不影响运行时生效
