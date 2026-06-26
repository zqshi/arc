"""系统设置服务 — 运行时配置覆盖 + .env 持久化 + adapter 缓存失效。

route 层只做参数校验, 配置变更的业务逻辑收敛于此。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from arc.config import settings

logger = logging.getLogger(__name__)

# 配置字段 → .env 变量名映射 (config env_prefix=ARC_, 故持久化 key 须带 ARC_ 前缀,
# 否则重启后读不回 → 配置变更只在运行时生效不持久。波次2 修复既有 LLM prefix 遗漏 + 补 agent)
_ENV_KEY_MAP = {
    "llm_provider": "ARC_LLM_PROVIDER",
    "openai_api_key": "ARC_OPENAI_API_KEY",
    "openai_base_url": "ARC_OPENAI_BASE_URL",
    "openai_model": "ARC_OPENAI_MODEL",
    "anthropic_api_key": "ARC_ANTHROPIC_API_KEY",
    "anthropic_base_url": "ARC_ANTHROPIC_BASE_URL",
    "anthropic_model": "ARC_ANTHROPIC_MODEL",
    "deepseek_api_key": "ARC_DEEPSEEK_API_KEY",
    "deepseek_base_url": "ARC_DEEPSEEK_BASE_URL",
    "deepseek_model": "ARC_DEEPSEEK_MODEL",
    "openhands_url": "ARC_OPENHANDS_URL",
    "openhands_api_key": "ARC_OPENHANDS_API_KEY",
    "codex_api_key": "ARC_CODEX_API_KEY",
    "codex_base_url": "ARC_CODEX_BASE_URL",
    "claude_code_path": "ARC_CLAUDE_CODE_PATH",
    "claude_code_work_dir": "ARC_CLAUDE_CODE_WORK_DIR",
    "claude_code_model": "ARC_CLAUDE_CODE_MODEL",
    "cursor_cli_path": "ARC_CURSOR_CLI_PATH",
}

# 涉 agent adapter 的字段 → update 后需重建 AgentRegistry
_AGENT_FIELDS = {
    "openhands_url", "openhands_api_key", "codex_api_key", "codex_base_url",
    "claude_code_path", "claude_code_work_dir", "claude_code_model", "cursor_cli_path",
}


class SettingsService:
    """LLM 设置的运行时变更与持久化。

    职责:
    1. 覆盖运行时 settings 对象
    2. 将变更持久化到 .env 文件 (ENV_FILE 优先, 回退 backend 根 .env)
    3. 失效 adapter 池缓存, 下次请求重建 adapter
    """

    def __init__(self, settings_obj=None, env_path: Path | None = None) -> None:
        self._settings = settings_obj if settings_obj is not None else settings
        self._env_path = env_path

    async def update(self, updates: dict) -> dict:
        """应用配置变更: 运行时覆盖 → 持久化 → 失效缓存 → (涉agent)重建registry。"""
        self._apply_runtime(updates)
        self._persist_to_env(updates)
        await self._invalidate_adapter_cache()
        self._maybe_reload_agent_registry(updates)
        return {
            "status": "updated",
            "llm_provider": self._settings.llm_provider,
            "updated_fields": list(updates.keys()),
        }

    def _apply_runtime(self, updates: dict) -> None:
        """覆盖运行时 settings 对象的对应字段。"""
        for key, value in updates.items():
            if value is not None and hasattr(self._settings, key):
                setattr(self._settings, key, value)

    def _persist_to_env(self, updates: dict) -> None:
        """将更新的配置写入 .env 文件 (已存在的 key 原位更新, 新 key 追加)。"""
        env_path = self._resolve_env_path()
        try:
            lines = env_path.read_text().splitlines() if env_path.exists() else []
        except Exception:
            lines = []

        existing_keys: dict[str, int] = {}
        for i, line in enumerate(lines):
            if "=" in line and not line.strip().startswith("#"):
                k = line.split("=", 1)[0].strip()
                existing_keys[k] = i

        for field, value in updates.items():
            if value is None:
                continue
            env_key = _ENV_KEY_MAP.get(field, f"ARC_{field.upper()}")
            if env_key in existing_keys:
                lines[existing_keys[env_key]] = f"{env_key}={value}"
            else:
                lines.append(f"{env_key}={value}")

        try:
            env_path.write_text("\n".join(lines) + "\n")
        except Exception:
            logger.warning("Failed to persist settings to %s", env_path)

    def _resolve_env_path(self) -> Path:
        """定位 .env 文件: ENV_FILE 环境变量优先, 回退 backend 根 .env。"""
        if self._env_path is not None:
            return self._env_path
        env_path = Path(os.environ.get("ENV_FILE", ".env"))
        if not env_path.exists():
            backend_env = Path(__file__).resolve().parents[4] / ".env"
            if backend_env.exists():
                env_path = backend_env
        return env_path

    async def _invalidate_adapter_cache(self) -> None:
        """清除 adapter 池缓存, 下次请求用新配置重建。"""
        try:
            from arc.application.ai.adapter_pool import adapter_pool

            await adapter_pool.shutdown()
        except Exception:
            logger.warning("Failed to invalidate adapter pool cache", exc_info=True)

    def _maybe_reload_agent_registry(self, updates: dict) -> None:
        """涉 agent adapter 字段时原地重建 AgentRegistry (skill 运行时配置生效)。"""
        if not (_AGENT_FIELDS & set(updates.keys())):
            return
        try:
            from arc.application.agent.registry import agent_registry

            agent_registry.reload()
            logger.info(
                "AgentRegistry reloaded: %s",
                [a.value for a in agent_registry.available_agents()],
            )
        except Exception:
            logger.warning("Failed to reload agent registry", exc_info=True)
