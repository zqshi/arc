import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conventions: Mapped[str | None] = mapped_column(Text, nullable=True)
    codebase_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_fingerprint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="idle", server_default="idle")
    scan_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    process_constraint: Mapped[str] = mapped_column(
        String(20), default="free", server_default="free",
    )
    project_type: Mapped[str] = mapped_column(
        String(30), default="static_site", server_default="static_site",
    )
    process_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pipeline_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    conversation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    domain_model: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    domain_model_history: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, server_default="[]",
    )
    context_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 项目宪章 (v6.3.0) — 系统按 project_type 生成的意图驱动治理规范 (ProjectCharter.to_dict)
    charter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    github_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_webhook_secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    github_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 签名凭证 (v6.1.0) — 按平台加密存储 (Fernet base64 token)
    enc_apple_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    enc_win_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    enc_android_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 签名凭证 (v6.19 T7/T10) — iOS / 鸿蒙 按平台加密存储
    enc_ios_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    enc_harmony_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 分发凭证 (v6.2.0) — 按渠道加密存储 (与签名凭证独立)
    enc_appstore_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    enc_playstore_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    enc_tauri_updater_creds: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v6.20 L5: 项目级 LLM 凭证指针 (FK → llm_providers.id, nullable)
    llm_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VersionModel(TimestampMixin, Base):
    __tablename__ = "versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planning")
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    prototype_preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deploy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
