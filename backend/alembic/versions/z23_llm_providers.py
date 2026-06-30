"""v6.20 L2: llm_providers 表 — 用户级多厂商 LLM 凭证。

支持添加多个 LLM 厂商 (openai/deepseek/anthropic/ollama/qwen/moonshot/custom),
api_key Fernet 加密 (复用 signing_secret_key), models 缓存 verify 时拉取的模型清单。
部分唯一索引保证每用户至多一个 is_default=true (全局默认互斥)。

Revision ID: z23_llm_providers
Revises: z22_role_default_member
Create Date: 2026-06-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "z23_llm_providers"
down_revision = "z22_role_default_member"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("api_key_enc", sa.Text, nullable=False),
        sa.Column("models", postgresql.JSONB, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_providers_user_id", "llm_providers", ["user_id"])
    # 部分唯一索引: 每用户至多一个 is_default=true (全局默认互斥)
    op.create_index(
        "uq_llm_providers_user_default",
        "llm_providers",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_llm_providers_user_default", table_name="llm_providers")
    op.drop_index("ix_llm_providers_user_id", table_name="llm_providers")
    op.drop_table("llm_providers")
