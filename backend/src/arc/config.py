from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Arc"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://zqs@localhost:5432/arc"
    database_echo: bool = False

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173", "http://localhost:5174",
        "http://localhost:5175", "http://localhost:5176",
    ]

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

    model_config = {"env_prefix": "ARC_", "env_file": ".env"}


settings = Settings()
