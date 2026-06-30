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

    # Redis (v6.7) — 跨进程事件总线, 启用多 worker 的前置
    # 空 = 退回进程内 InMemoryEventBus (单 worker / dev / 单测默认)
    # 生产多 worker 部署必配, 如 redis://redis:6379/0
    redis_url: str = ""

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
    sandbox_default_mode: str = "none"  # none | approval_gate | docker | open_sandbox
    # OpenSandbox (v6.7) — 云沙箱后端, sandbox_default_mode=open_sandbox 时启用
    # 空 server_url → 单机默认 (opensandbox-server 本地); 生产填真实地址
    opensandbox_url: str = ""
    opensandbox_api_key: str = ""
    opensandbox_image: str = "python:3.12-slim"
    # 覆盖默认构建镜像映射, key 格式 "{project_type}:{build_target}"
    # 开发态留空 → DEFAULT_BUILD_IMAGES 注册表 (本地 make 构建的 arc/xxx 本地名)
    # 生产环境: docker-publish.yml 的 build-builder-images job 在 release tag 时
    #   发布 ghcr.io/<owner>/<repo>-{tauri,web,android}-builder:latest, 此处覆盖映射:
    #   {"binary_app:tauri_linux": "ghcr.io/<owner>/<repo>-tauri-builder:latest",
    #    "binary_app:web": "ghcr.io/<owner>/<repo>-web-builder:latest",
    #    "binary_app:capacitor_apk": "ghcr.io/<owner>/<repo>-android-builder:latest"}
    sandbox_builder_images: dict[str, str] = {}

    # GitHub Actions CI 编排 (v6.19 T3) — CI target (windows/ios/harmony) 构建走 GHA workflow。
    # 空 token → CI target 构建降级报错 (非 docker target 不受影响)。
    # token 需 actions:write 权限 (触发 workflow_dispatch); owner/repo 为承载产物构建
    # workflow (build-client-artifacts.yml) 的仓库。
    gha_token: str = ""
    gha_owner: str = ""
    gha_repo: str = ""

    # Object Storage (S3-compatible: MinIO / AWS S3 / Aliyun OSS)
    storage_endpoint: str = ""
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_bucket: str = "arc-previews"
    storage_public_url: str = ""
    # 本地存储模式(无 storage_endpoint 时)的预览静态目录; 容器须指向可写卷
    # (如 /app/data/static/previews)。空则回退 arc 包目录(dev 可写, 但容器内
    # site-packages 只读 → PermissionError)。生产推荐配 storage_endpoint 走对象存储
    preview_static_dir: str = ""

    # Deployment
    deploy_path_prefix: str = "deployments"
    deploy_cdn_domain: str = ""
    deploy_max_file_size: int = 50 * 1024 * 1024  # 50 MB

    # Signing (v6.1.0) — 凭证项目维度加密存储 (见 infrastructure/crypto.py)
    # 此为 Fernet 密钥, 加密各项目的签名凭证。空=dev 降级明文 (生产必配)
    # 生成: python -c "from cryptography.fernet import Fernet;
    #         print(Fernet.generate_key().decode())"
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

    # Observability — /metrics bearer token (A2 投产门禁)
    # 空=不校验 (dev/集群内网); 生产配随机 token, scraper 带 Authorization: Bearer <token>
    prometheus_token: str = ""

    model_config = {"env_prefix": "ARC_", "env_file": ".env"}


settings = Settings()
