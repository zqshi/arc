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
    sms_mock_mode: bool = False

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

    # Worker model — cheap model for sub-agent read-only tasks
    worker_llm_provider: str = ""  # empty = same as llm_provider
    worker_model: str = ""  # empty = same as main model (e.g. "gpt-4o-mini")
    max_concurrent_workers: int = 3

    # Sandbox
    sandbox_default_mode: str = "none"  # none | approval_gate | docker
    # 覆盖默认构建镜像映射, key 格式 "{project_type}:{build_target}"
    # 例: {"binary_app:tauri_linux": "registry.example.com/tauri:v2"}
    # 留空则用 domain/sandbox/build_images.py 的 DEFAULT_BUILD_IMAGES 注册表
    sandbox_builder_images: dict[str, str] = {}

    # Object Storage (S3-compatible: MinIO / AWS S3 / Aliyun OSS)
    storage_endpoint: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_bucket: str = "arc-previews"
    storage_public_url: str = ""

    # Deployment
    deploy_path_prefix: str = "deployments"
    deploy_cdn_domain: str = ""
    deploy_max_file_size: int = 50 * 1024 * 1024  # 50 MB

    # Signing (v6.1.0) — 凭证项目维度加密存储 (见 infrastructure/crypto.py)
    # 此为 Fernet 密钥, 加密各项目的签名凭证。空=dev 降级明文 (生产必配)
    # 生成: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    signing_secret_key: str = ""

    # BaaS (v5.6.0) — Supabase PG 连接
    # 留空则复用 Arc 的 database_url (dev: 生成的应用 schema 与 Arc 元数据同库,
    # 靠 arc_{project_id} 前缀隔离); 生产填真实 Supabase Postgres DSN
    supabase_db_url: str = ""
    supabase_schema_prefix: str = "arc_"  # schema 隔离前缀, 需与 BaasSchema 约定一致
    # 注入前端工程的 Supabase 连接信息 (v5.6.0 T12)
    # dev 默认指向本地 PostgREST; 生产填真实 Supabase anon key
    supabase_anon_key: str = "dev-anon-key"
    supabase_api_url: str = "http://localhost:54321"  # PostgREST endpoint 给前端用

    model_config = {"env_prefix": "ARC_", "env_file": ".env"}


settings = Settings()
