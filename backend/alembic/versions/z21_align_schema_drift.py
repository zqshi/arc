"""align schema drift (M1)

对齐 ORM 模型与 DB schema 的历史漂移 (v6.19 M1 投产软阻断):
1. nullable 收紧 — 模型 NOT NULL, DB nullable=True (字段都有 server_default 或先 backfill)
2. unique 表达对齐 — DB unique index vs 模型 UniqueConstraint 等价转换
3. drop 重复命名索引 — 同列两索引并存 (migration 自定义名 vs 模型 index=True 生成名),
   drop 旧名无损性能, 新名仍在
4. experience_feedback 命名对齐 — drop 缩写旧名 ix_exp_feedback_todo_id + create 全名
   ix_experience_feedback_todo_id 对齐模型

延续 7d587912c43d「不删性能索引, 只做安全对齐」精神。
注: review_feedbacks 曾被误判为死表 (实为 models/__init__.py 漏 import, 已补), 本 migration 不 drop 表。

Revision ID: z21_align_schema_drift
Revises: z20_ios_harmony_creds
Create Date: 2026-06-30
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "z21_align_schema_drift"
down_revision = "z20_ios_harmony_creds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- D1: nullable 收紧 (模型 NOT NULL, DB nullable=True; 字段都有 server_default) --

    # baas_instances
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "baas_instances", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            existing_server_default=sa.text("now()"),
        )

    # deployments
    op.alter_column(
        "deployments", "build_command",
        existing_type=sa.String(length=200),
        nullable=False,
        existing_server_default=sa.text("'npm run build'::character varying"),
    )
    op.alter_column(
        "deployments", "artifact_path",
        existing_type=sa.String(length=200),
        nullable=False,
        existing_server_default=sa.text("'dist'::character varying"),
    )
    op.alter_column(
        "deployments", "files_uploaded",
        existing_type=sa.Integer(),
        nullable=False,
        existing_server_default=sa.text("0"),
    )
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "deployments", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            existing_server_default=sa.text("now()"),
        )

    # domain_templates
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "domain_templates", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            existing_server_default=sa.text("now()"),
        )

    # projects.process_constraint
    op.alter_column(
        "projects", "process_constraint",
        existing_type=sa.String(length=20),
        nullable=False,
        existing_server_default=sa.text("'free'::character varying"),
    )

    # review_feedbacks.model_version/status 无 server_default (Python default=), 先 backfill 再 alter
    op.execute("UPDATE review_feedbacks SET model_version = 0 WHERE model_version IS NULL")
    op.execute("UPDATE review_feedbacks SET status = 'pending' WHERE status IS NULL")
    op.alter_column(
        "review_feedbacks", "model_version",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "review_feedbacks", "status",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "review_feedbacks", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            existing_server_default=sa.text("now()"),
        )

    # -- D2: unique 表达对齐 (DB unique index → 模型 UniqueConstraint, 等价转换) --

    # baas_instances: DB uq_constraint + 非unique index → 模型 unique index (index=True+unique=True)
    op.drop_constraint("uq_baas_instances_project_id", "baas_instances", type_="unique")
    op.drop_index("ix_baas_instances_project_id", table_name="baas_instances")
    op.create_index(
        "ix_baas_instances_project_id", "baas_instances", ["project_id"], unique=True,
    )

    # users: DB unique index (idx_users_phone/username) → 模型 UniqueConstraint (具名 uq_users_*)
    op.drop_index("idx_users_phone", table_name="users")
    op.drop_index("idx_users_username", table_name="users")
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    # -- D3: drop 重复命名索引 (同列新名索引已在, drop 旧名无损性能) --

    # idx_ 前缀旧名 (i2k6gh589012 建) vs 模型 index=True 生成 ix_ 新名
    op.drop_index("idx_experiences_user_id", table_name="experiences")
    op.drop_index("idx_todos_user_id", table_name="todos")
    op.drop_index("idx_projects_user_id", table_name="projects")
    # 缩写表名旧名 (z1/s6a9 建, 7d587912c43d keep old) vs 模型生成全名 (7d587912c43d 建新名)
    op.drop_index("ix_org_members_org_id", table_name="organization_members")
    op.drop_index("ix_org_members_user_id", table_name="organization_members")
    op.drop_index("ix_todo_deps_todo_id", table_name="todo_dependencies")
    op.drop_index("ix_todo_deps_depends_on_id", table_name="todo_dependencies")

    # experience_feedback: 命名对齐 (缩写 ix_exp_feedback_todo_id → 全名 ix_experience_feedback_todo_id)
    op.drop_index("ix_exp_feedback_todo_id", table_name="experience_feedback")
    op.create_index(
        "ix_experience_feedback_todo_id", "experience_feedback", ["todo_id"],
    )


def downgrade() -> None:
    # D3 reverse: recreate 旧名索引 (if_not_exists 幂等), drop 新名
    op.drop_index("ix_experience_feedback_todo_id", table_name="experience_feedback")
    op.create_index(
        "ix_exp_feedback_todo_id", "experience_feedback", ["todo_id"], if_not_exists=True,
    )
    op.create_index(
        "ix_todo_deps_depends_on_id", "todo_dependencies", ["depends_on_id"], if_not_exists=True,
    )
    op.create_index(
        "ix_todo_deps_todo_id", "todo_dependencies", ["todo_id"], if_not_exists=True,
    )
    op.create_index(
        "ix_org_members_user_id", "organization_members", ["user_id"], if_not_exists=True,
    )
    op.create_index(
        "ix_org_members_org_id", "organization_members", ["organization_id"], if_not_exists=True,
    )
    op.create_index(
        "idx_projects_user_id", "projects", ["user_id"], if_not_exists=True,
    )
    op.create_index(
        "idx_todos_user_id", "todos", ["user_id"], if_not_exists=True,
    )
    op.create_index(
        "idx_experiences_user_id", "experiences", ["user_id"], if_not_exists=True,
    )

    # D2 reverse
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_constraint("uq_users_phone", "users", type_="unique")
    op.create_index("idx_users_username", "users", ["username"], unique=True)
    op.create_index("idx_users_phone", "users", ["phone"], unique=True)

    op.drop_index("ix_baas_instances_project_id", table_name="baas_instances")
    op.create_unique_constraint(
        "uq_baas_instances_project_id", "baas_instances", ["project_id"],
    )
    op.create_index(
        "ix_baas_instances_project_id", "baas_instances", ["project_id"],
    )

    # D1 reverse: nullable 放回 True
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "review_feedbacks", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            existing_server_default=sa.text("now()"),
        )
    op.alter_column(
        "review_feedbacks", "status",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "review_feedbacks", "model_version",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "projects", "process_constraint",
        existing_type=sa.String(length=20),
        nullable=True,
        existing_server_default=sa.text("'free'::character varying"),
    )
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "domain_templates", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            existing_server_default=sa.text("now()"),
        )
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "deployments", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            existing_server_default=sa.text("now()"),
        )
    op.alter_column(
        "deployments", "files_uploaded",
        existing_type=sa.Integer(),
        nullable=True,
        existing_server_default=sa.text("0"),
    )
    op.alter_column(
        "deployments", "artifact_path",
        existing_type=sa.String(length=200),
        nullable=True,
        existing_server_default=sa.text("'dist'::character varying"),
    )
    op.alter_column(
        "deployments", "build_command",
        existing_type=sa.String(length=200),
        nullable=True,
        existing_server_default=sa.text("'npm run build'::character varying"),
    )
    for col in ("created_at", "updated_at"):
        op.alter_column(
            "baas_instances", col,
            existing_type=postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            existing_server_default=sa.text("now()"),
        )
