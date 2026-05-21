from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Arc"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://zqs@localhost:5432/arc"
    database_echo: bool = False

    # CORS — explicitly configure in .env for production
    cors_origins: list[str] = []

    # Database pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # Auth / JWT
    jwt_secret: str = ""
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    sms_mock_mode: bool = True

    # LLM
    llm_provider: str = "openai"  # openai | anthropic | deepseek
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # OpenHands
    openhands_url: str = "http://localhost:3000"
    openhands_api_key: str = ""

    # Codex
    codex_api_key: str = ""
    codex_base_url: str = "https://api.openai.com/v1"

    # Claude Code
    claude_code_path: str = ""
    claude_code_work_dir: str = ""
    claude_code_model: str = ""

    # Cursor
    cursor_cli_path: str = ""

    # Agent orchestration — per-phase agent override (empty = use default)
    agent_default: str = "openhands"
    agent_development: str = ""
    agent_testing: str = ""
    agent_deployment: str = ""

    model_config = {"env_prefix": "ARC_", "env_file": ".env"}


settings = Settings()
