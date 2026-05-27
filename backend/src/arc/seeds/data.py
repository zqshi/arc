"""Full-chain seed data insertion for Arc demo.

> 行数超限例外: 纯 seed 插入函数, 全部为过程式 SQL INSERT, 不含业务逻辑。
> 数据常量已拆分到 data_artifacts.py / data_messages.py。

Called from main.py on first startup for each seed user. All data is inserted via raw SQL
to avoid domain validation (seed data includes mid-pipeline states).
Uses random UUIDs so the function can be called for multiple users without conflicts.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from arc.seeds.data_artifacts import (
    TODO1_REQUIREMENT_SPEC,
    TODO1_UI_DESIGN,
    TODO2_REQUIREMENT_SPEC,
    TODO2_UI_DESIGN,
    TODO2_TECH_ARCHITECTURE,
    TODO2_DEV_REPORT,
    TODO2_TEST_REPORT,
    TODO2_DEPLOY_REPORT,
    TODO2_EXPERIENCE_CARD,
    TODO6_TECH_ARCHITECTURE,
    TODO6_REQUIREMENT_SPEC,
    TODO9_REQUIREMENT_SPEC,
    TODO9_UI_DESIGN,
    TODO9_TECH_ARCHITECTURE,
    TODO9_DEV_REPORT,
)
from arc.seeds.data_messages import (
    TODO1_CLAR_MESSAGES,
    TODO1_UI_MESSAGES,
    TODO2_CLAR_MESSAGES,
    TODO2_UI_MESSAGES,
    TODO2_ARCH_MESSAGES,
    TODO2_EXTRACT_MESSAGES,
    TODO6_CLAR_MESSAGES,
    TODO6_ARCH_MESSAGES,
    TODO9_CLAR_MESSAGES,
    TODO9_UI_MESSAGES,
    TODO9_ARCH_MESSAGES,
    TODO11_CLAR_MESSAGES,
    EXPERIENCES_DATA,
)


# ═══════════════════════════════════════════════════════════════════
# Main seed function
# ═══════════════════════════════════════════════════════════════════


async def create_seed_data(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Insert full demo data for the given user via raw SQL."""

    now = datetime.now(UTC)

    # ── Generate all IDs upfront ────────────────────────────────
    project1_id = uuid.uuid4()
    project2_id = uuid.uuid4()
    ver1_id, ver2_id, ver3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo1_id, todo2_id, todo3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo4_id, todo5_id = uuid.uuid4(), uuid.uuid4()
    todo6_id, todo7_id, todo8_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    # Todo1 pipeline phase IDs
    t1_phase = {
        pt: uuid.uuid4()
        for pt in [
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        ]
    }
    # Todo2 pipeline phase IDs
    t2_phase = {
        pt: uuid.uuid4()
        for pt in [
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        ]
    }
    # Todo6 pipeline phase IDs
    t6_phase = {
        pt: uuid.uuid4()
        for pt in [
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        ]
    }

    # Conversation IDs
    t1_conv = {"clarification": uuid.uuid4(), "ui_design": uuid.uuid4()}
    t2_conv = {
        "clarification": uuid.uuid4(),
        "ui_design": uuid.uuid4(),
        "architecture": uuid.uuid4(),
        "extraction": uuid.uuid4(),
    }
    t6_conv = {"clarification": uuid.uuid4(), "architecture": uuid.uuid4()}

    # Agent session IDs for todo2
    t2_agent = {"development": uuid.uuid4(), "testing": uuid.uuid4(), "deployment": uuid.uuid4()}

    # ── Helper ──────────────────────────────────────────────────

    async def _insert(table: str, values: dict) -> None:
        cols = ", ".join(f'"{k}"' if k == "order" else k for k in values.keys())
        params = ", ".join(f":{k}" for k in values.keys())
        await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)

    async def _insert_messages(
        conv_id: uuid.UUID, messages: list[tuple[str, str]], base_time: datetime
    ) -> None:
        for i, (role, content) in enumerate(messages):
            await _insert(
                "messages",
                {
                    "id": uuid.uuid4(),
                    "conversation_id": conv_id,
                    "role": role,
                    "content": content,
                    "created_at": base_time + timedelta(minutes=i * 3),
                },
            )

    # ═══════════════════════════════════════════════════════════
    # Project 1: 数据管理后台
    # ═══════════════════════════════════════════════════════════

    await _insert(
        "projects",
        {
            "id": project1_id,
            "user_id": user_id,
            "name": "数据管理后台",
            "description": "企业级数据管理与分析平台，支持多维度数据导出、可视化看板和权限管理",
            "tech_stack": "React + FastAPI + PostgreSQL + Celery",
            "status": "active",
            "created_at": now - timedelta(days=21),
            "updated_at": now,
        },
    )

    # Version v1.0 (active)
    await _insert(
        "versions",
        {
            "id": ver1_id,
            "project_id": project1_id,
            "name": "v1.0",
            "goal": "核心导出功能 + 权限体系",
            "status": "active",
            "order": 1,
            "created_at": now - timedelta(days=21),
            "updated_at": now,
        },
    )

    # Version v1.1 (planning)
    await _insert(
        "versions",
        {
            "id": ver2_id,
            "project_id": project1_id,
            "name": "v1.1",
            "goal": "可视化看板 + 定时导出",
            "status": "planning",
            "order": 2,
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    # ── Todo1: 实现批量数据导出功能 (active, at ui_design) ──

    await _insert(
        "todos",
        {
            "id": todo1_id,
            "user_id": user_id,
            "project_id": project1_id,
            "version_id": ver1_id,
            "title": "实现批量数据导出功能",
            "description": "支持管理员按日期范围导出用户行为/订单/商品数据为CSV，异步执行+通知下载",
            "status": "active",
            "priority": 1,
            "current_phase": "ui_design",
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "核心功能", "color": "#6366F1"}]
            ),
            "created_at": now - timedelta(days=10),
            "updated_at": now,
        },
    )

    # Conversations (must exist before pipeline_phases FK)
    for purpose, conv_id in t1_conv.items():
        await _insert(
            "conversations",
            {
                "id": conv_id,
                "todo_id": todo1_id,
                "purpose": purpose,
                "created_at": now - timedelta(days=10),
                "updated_at": now,
            },
        )

    # Pipeline phases
    t1_phases_data = [
        ("clarification", "confirmed", t1_conv["clarification"]),
        ("ui_design", "awaiting_confirm", t1_conv["ui_design"]),
        ("architecture", "pending", None),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t1_phases_data:
        await _insert(
            "pipeline_phases",
            {
                "id": t1_phase[pt],
                "todo_id": todo1_id,
                "phase_type": pt,
                "status": status,
                "conversation_id": cid,
                "created_at": now - timedelta(days=10),
                "updated_at": now,
            },
        )

    # Messages
    await _insert_messages(t1_conv["clarification"], TODO1_CLAR_MESSAGES, now - timedelta(days=10))
    await _insert_messages(t1_conv["ui_design"], TODO1_UI_MESSAGES, now - timedelta(days=7))

    # Artifacts
    await _insert(
        "artifacts",
        {
            "id": uuid.uuid4(),
            "todo_id": todo1_id,
            "phase_id": t1_phase["clarification"],
            "artifact_type": "requirement_spec",
            "content": json.dumps(TODO1_REQUIREMENT_SPEC),
            "version": 1,
            "is_confirmed": True,
            "confirmed_at": now - timedelta(days=8),
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=8),
        },
    )
    await _insert(
        "artifacts",
        {
            "id": uuid.uuid4(),
            "todo_id": todo1_id,
            "phase_id": t1_phase["ui_design"],
            "artifact_type": "ui_design",
            "content": json.dumps(TODO1_UI_DESIGN),
            "version": 1,
            "is_confirmed": False,
            "confirmed_at": None,
            "created_at": now - timedelta(days=6),
            "updated_at": now,
        },
    )

    # ── Todo2: 用户权限与角色管理 (done, all phases completed) ──

    await _insert(
        "todos",
        {
            "id": todo2_id,
            "user_id": user_id,
            "project_id": project1_id,
            "version_id": ver1_id,
            "title": "用户权限与角色管理",
            "description": "RBAC 权限模型，支持管理员/运营/只读三种角色，控制数据导出和看板访问权限",
            "status": "done",
            "priority": 1,
            "current_phase": "extraction",
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "安全", "color": "#EF4444"}]
            ),
            "created_at": now - timedelta(days=18),
            "updated_at": now - timedelta(days=3),
        },
    )

    # Conversations
    for purpose, conv_id in t2_conv.items():
        await _insert(
            "conversations",
            {
                "id": conv_id,
                "todo_id": todo2_id,
                "purpose": purpose,
                "created_at": now - timedelta(days=18),
                "updated_at": now - timedelta(days=3),
            },
        )

    # Step 1: Pipeline phases first (without agent_session_id, breaks circular FK)
    t2_phases_data = [
        ("clarification", "confirmed", t2_conv["clarification"]),
        ("ui_design", "confirmed", t2_conv["ui_design"]),
        ("architecture", "confirmed", t2_conv["architecture"]),
        ("development", "confirmed", None),
        ("testing", "confirmed", None),
        ("deployment", "confirmed", None),
        ("extraction", "confirmed", t2_conv["extraction"]),
    ]
    for pt, status, cid in t2_phases_data:
        await _insert(
            "pipeline_phases",
            {
                "id": t2_phase[pt],
                "todo_id": todo2_id,
                "phase_type": pt,
                "status": status,
                "conversation_id": cid,
                "created_at": now - timedelta(days=18),
                "updated_at": now - timedelta(days=3),
            },
        )

    # Step 2: Agent sessions (now pipeline_phases exist for FK)
    agent_sessions_data = [
        (
            t2_agent["development"],
            "development",
            "openhands",
            "completed",
            {
                "task": "实现RBAC权限体系：JWT鉴权中间件、角色装饰器、前端AuthContext和ProtectedRoute",
                "repo_url": "https://github.com/example/data-admin",
            },
            {
                "status": "success",
                "files_changed": 8,
                "tests_added": 27,
                "lines_added": 847,
                "lines_deleted": 23,
            },
            now - timedelta(days=12),
            now - timedelta(days=12, hours=-2, minutes=-25),
        ),
        (
            t2_agent["testing"],
            "testing",
            "openhands",
            "completed",
            {
                "task": "测试RBAC权限体系：认证流程、鉴权中间件、前端权限控制的自动化测试",
                "test_framework": "pytest + playwright",
            },
            {
                "status": "success",
                "total_tests": 27,
                "passed": 27,
                "failed": 0,
                "coverage_line": 89.2,
            },
            now - timedelta(days=10),
            now - timedelta(days=10, hours=-1),
        ),
        (
            t2_agent["deployment"],
            "deployment",
            "openhands",
            "completed",
            {
                "task": "部署RBAC权限体系：数据库迁移、后端服务更新、前端构建部署",
                "environment": "production",
            },
            {"status": "success", "migration_applied": True, "rollback_available": True},
            now - timedelta(days=8),
            now - timedelta(days=8, hours=-0, minutes=-30),
        ),
    ]
    for (
        sess_id,
        phase,
        agent_type,
        status,
        context,
        result,
        started,
        completed,
    ) in agent_sessions_data:
        await _insert(
            "agent_sessions",
            {
                "id": sess_id,
                "todo_id": todo2_id,
                "phase_id": t2_phase[phase],
                "agent_type": agent_type,
                "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
                "status": status,
                "task_context": json.dumps(context),
                "result_summary": json.dumps(result),
                "error_reason": "",
                "started_at": started,
                "completed_at": completed,
                "created_at": started,
                "updated_at": completed,
            },
        )

    # Step 3: Backfill agent_session_id on pipeline_phases
    for phase_name, sess_id in t2_agent.items():
        await db.execute(
            text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
            {"aid": sess_id, "pid": t2_phase[phase_name]},
        )

    # Messages
    await _insert_messages(t2_conv["clarification"], TODO2_CLAR_MESSAGES, now - timedelta(days=18))
    await _insert_messages(t2_conv["ui_design"], TODO2_UI_MESSAGES, now - timedelta(days=16))
    await _insert_messages(t2_conv["architecture"], TODO2_ARCH_MESSAGES, now - timedelta(days=15))
    await _insert_messages(t2_conv["extraction"], TODO2_EXTRACT_MESSAGES, now - timedelta(days=4))

    # Artifacts (all 7 types)
    t2_artifacts = [
        (
            "requirement_spec",
            t2_phase["clarification"],
            TODO2_REQUIREMENT_SPEC,
            True,
            now - timedelta(days=17),
        ),
        ("ui_design", t2_phase["ui_design"], TODO2_UI_DESIGN, True, now - timedelta(days=15)),
        (
            "tech_architecture",
            t2_phase["architecture"],
            TODO2_TECH_ARCHITECTURE,
            True,
            now - timedelta(days=14),
        ),
        ("dev_report", t2_phase["development"], TODO2_DEV_REPORT, True, now - timedelta(days=11)),
        ("test_report", t2_phase["testing"], TODO2_TEST_REPORT, True, now - timedelta(days=9)),
        (
            "deploy_report",
            t2_phase["deployment"],
            TODO2_DEPLOY_REPORT,
            True,
            now - timedelta(days=7),
        ),
        (
            "experience_card",
            t2_phase["extraction"],
            TODO2_EXPERIENCE_CARD,
            True,
            now - timedelta(days=4),
        ),
    ]
    for art_type, phase_id, content, confirmed, conf_at in t2_artifacts:
        await _insert(
            "artifacts",
            {
                "id": uuid.uuid4(),
                "todo_id": todo2_id,
                "phase_id": phase_id,
                "artifact_type": art_type,
                "content": json.dumps(content),
                "version": 1,
                "is_confirmed": confirmed,
                "confirmed_at": conf_at,
                "created_at": conf_at - timedelta(days=1),
                "updated_at": conf_at,
            },
        )

    # ── Todo3: 导出任务队列与并发控制 (pending) ──

    await _insert(
        "todos",
        {
            "id": todo3_id,
            "user_id": user_id,
            "project_id": project1_id,
            "version_id": ver1_id,
            "title": "导出任务队列与并发控制",
            "description": "基于 Celery 的异步任务队列，限制同时3个导出任务，支持任务状态查询和重试",
            "status": "pending",
            "priority": 2,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "性能", "color": "#F59E0B"}]
            ),
            "created_at": now - timedelta(days=7),
            "updated_at": now,
        },
    )

    # ── Todo4 & Todo5: v1.1 planning todos ──

    v2_todos = [
        (
            todo4_id,
            "数据可视化看板",
            "用 ECharts 构建核心指标看板：日活、留存、转化漏斗，支持日期范围筛选",
            [{"label": "前端", "color": "#34D399"}, {"label": "可视化", "color": "#A78BFA"}],
        ),
        (
            todo5_id,
            "定时导出与邮件通知",
            "支持配置周期性导出计划（日/周/月），导出完成后自动发送邮件通知",
            [{"label": "后端", "color": "#4A9FD8"}],
        ),
    ]
    for i, (tid, title, desc, tags) in enumerate(v2_todos):
        await _insert(
            "todos",
            {
                "id": tid,
                "user_id": user_id,
                "project_id": project1_id,
                "version_id": ver2_id,
                "title": title,
                "description": desc,
                "status": "pending",
                "priority": i + 2,
                "current_phase": None,
                "tags": json.dumps(tags),
                "created_at": now - timedelta(days=5),
                "updated_at": now - timedelta(days=5),
            },
        )

    # ═══════════════════════════════════════════════════════════
    # Project 2: 智能客服系统
    # ═══════════════════════════════════════════════════════════

    await _insert(
        "projects",
        {
            "id": project2_id,
            "user_id": user_id,
            "name": "智能客服系统",
            "description": "基于 RAG 的企业知识库客服，支持多轮对话和工单自动分流",
            "tech_stack": "Next.js + Python + Milvus + LangChain",
            "status": "active",
            "created_at": now - timedelta(days=14),
            "updated_at": now - timedelta(days=1),
        },
    )

    await _insert(
        "versions",
        {
            "id": ver3_id,
            "project_id": project2_id,
            "name": "v1.0",
            "goal": "知识库检索 + 多轮对话 + 客服工作台",
            "status": "active",
            "order": 1,
            "created_at": now - timedelta(days=14),
            "updated_at": now - timedelta(days=1),
        },
    )

    # ── Todo6: 文档解析与向量化 (active, at architecture) ──

    await _insert(
        "todos",
        {
            "id": todo6_id,
            "user_id": user_id,
            "project_id": project2_id,
            "version_id": ver3_id,
            "title": "文档解析与向量化",
            "description": "支持 PDF/Markdown 文档切片和 embedding，接入 Milvus 向量库",
            "status": "active",
            "priority": 1,
            "current_phase": "architecture",
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "AI", "color": "#A78BFA"}]
            ),
            "created_at": now - timedelta(days=12),
            "updated_at": now - timedelta(days=1),
        },
    )

    # Conversations
    for purpose, conv_id in t6_conv.items():
        await _insert(
            "conversations",
            {
                "id": conv_id,
                "todo_id": todo6_id,
                "purpose": purpose,
                "created_at": now - timedelta(days=12),
                "updated_at": now,
            },
        )

    # Pipeline phases
    t6_phases_data = [
        ("clarification", "confirmed", t6_conv["clarification"]),
        ("ui_design", "skipped", None),
        ("architecture", "active", t6_conv["architecture"]),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t6_phases_data:
        await _insert(
            "pipeline_phases",
            {
                "id": t6_phase[pt],
                "todo_id": todo6_id,
                "phase_type": pt,
                "status": status,
                "conversation_id": cid,
                "created_at": now - timedelta(days=12),
                "updated_at": now,
            },
        )

    # Messages
    await _insert_messages(t6_conv["clarification"], TODO6_CLAR_MESSAGES, now - timedelta(days=11))
    await _insert_messages(t6_conv["architecture"], TODO6_ARCH_MESSAGES, now - timedelta(days=6))

    # Artifacts
    await _insert(
        "artifacts",
        {
            "id": uuid.uuid4(),
            "todo_id": todo6_id,
            "phase_id": t6_phase["clarification"],
            "artifact_type": "requirement_spec",
            "content": json.dumps(TODO6_REQUIREMENT_SPEC),
            "version": 1,
            "is_confirmed": True,
            "confirmed_at": now - timedelta(days=9),
            "created_at": now - timedelta(days=11),
            "updated_at": now - timedelta(days=9),
        },
    )
    await _insert(
        "artifacts",
        {
            "id": uuid.uuid4(),
            "todo_id": todo6_id,
            "phase_id": t6_phase["architecture"],
            "artifact_type": "tech_architecture",
            "content": json.dumps(TODO6_TECH_ARCHITECTURE),
            "version": 1,
            "is_confirmed": False,
            "confirmed_at": None,
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    # ── Todo7 & Todo8: pending todos ──

    p2_todos = [
        (
            todo7_id,
            "多轮对话管理",
            "维护对话上下文窗口，支持追问、澄清和话题切换，上下文窗口动态调整",
            [{"label": "后端", "color": "#4A9FD8"}],
        ),
        (
            todo8_id,
            "客服工作台前端",
            "客服人员的实时会话列表、快捷回复模板和工单转接界面",
            [{"label": "前端", "color": "#34D399"}, {"label": "UX", "color": "#EC4899"}],
        ),
    ]
    for tid, title, desc, tags in p2_todos:
        await _insert(
            "todos",
            {
                "id": tid,
                "user_id": user_id,
                "project_id": project2_id,
                "version_id": ver3_id,
                "title": title,
                "description": desc,
                "status": "pending",
                "priority": 2,
                "current_phase": None,
                "tags": json.dumps(tags),
                "created_at": now - timedelta(days=12),
                "updated_at": now - timedelta(days=1),
            },
        )

    # ═══════════════════════════════════════════════════════════
    # Project 3: 移动电商App
    # ═══════════════════════════════════════════════════════════

    project3_id = uuid.uuid4()
    ver4_id = uuid.uuid4()
    todo9_id, todo10_id = uuid.uuid4(), uuid.uuid4()
    t9_phase = {
        pt: uuid.uuid4()
        for pt in [
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        ]
    }
    t9_conv = {
        "clarification": uuid.uuid4(),
        "ui_design": uuid.uuid4(),
        "architecture": uuid.uuid4(),
    }
    t9_agent = {"development": uuid.uuid4()}

    await _insert(
        "projects",
        {
            "id": project3_id,
            "user_id": user_id,
            "name": "移动电商App",
            "description": "C端电商移动应用，涵盖商品搜索、个性化推荐、订单管理和支付系统",
            "tech_stack": "React Native + Node.js + MongoDB + Elasticsearch + Redis",
            "status": "active",
            "created_at": now - timedelta(days=30),
            "updated_at": now - timedelta(days=1),
        },
    )

    await _insert(
        "versions",
        {
            "id": ver4_id,
            "project_id": project3_id,
            "name": "v1.0",
            "goal": "商品搜索优化 + 个性化推荐",
            "status": "active",
            "order": 1,
            "created_at": now - timedelta(days=30),
            "updated_at": now - timedelta(days=1),
        },
    )

    # ── Todo9: 商品搜索优化 (active, at development) ──

    await _insert(
        "todos",
        {
            "id": todo9_id,
            "user_id": user_id,
            "project_id": project3_id,
            "version_id": ver4_id,
            "title": "商品搜索优化",
            "description": "基于 Elasticsearch 重构搜索系统，支持中文分词、同义词扩展和搜索联想",
            "status": "active",
            "priority": 1,
            "current_phase": "development",
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "搜索", "color": "#F59E0B"}]
            ),
            "created_at": now - timedelta(days=20),
            "updated_at": now - timedelta(days=1),
        },
    )

    for purpose, conv_id in t9_conv.items():
        await _insert(
            "conversations",
            {
                "id": conv_id,
                "todo_id": todo9_id,
                "purpose": purpose,
                "created_at": now - timedelta(days=20),
                "updated_at": now,
            },
        )

    t9_phases_data = [
        ("clarification", "confirmed", t9_conv["clarification"]),
        ("ui_design", "confirmed", t9_conv["ui_design"]),
        ("architecture", "confirmed", t9_conv["architecture"]),
        ("development", "confirmed", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t9_phases_data:
        await _insert(
            "pipeline_phases",
            {
                "id": t9_phase[pt],
                "todo_id": todo9_id,
                "phase_type": pt,
                "status": status,
                "conversation_id": cid,
                "created_at": now - timedelta(days=20),
                "updated_at": now,
            },
        )

    # Agent session for development
    await _insert(
        "agent_sessions",
        {
            "id": t9_agent["development"],
            "todo_id": todo9_id,
            "phase_id": t9_phase["development"],
            "agent_type": "openhands",
            "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
            "status": "completed",
            "task_context": json.dumps(
                {
                    "task": "基于Elasticsearch实现商品搜索：IK分词+同义词+联想词+筛选排序",
                    "repo_url": "https://github.com/example/ecommerce-app",
                }
            ),
            "result_summary": json.dumps(
                {
                    "status": "success",
                    "files_changed": 7,
                    "tests_added": 18,
                    "lines_added": 1236,
                    "lines_deleted": 89,
                }
            ),
            "error_reason": "",
            "started_at": now - timedelta(days=3),
            "completed_at": now - timedelta(days=3, hours=-3),
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=3, hours=-3),
        },
    )

    await db.execute(
        text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
        {"aid": t9_agent["development"], "pid": t9_phase["development"]},
    )

    await _insert_messages(t9_conv["clarification"], TODO9_CLAR_MESSAGES, now - timedelta(days=18))
    await _insert_messages(t9_conv["ui_design"], TODO9_UI_MESSAGES, now - timedelta(days=14))
    await _insert_messages(t9_conv["architecture"], TODO9_ARCH_MESSAGES, now - timedelta(days=10))

    t9_artifacts = [
        (
            "requirement_spec",
            t9_phase["clarification"],
            TODO9_REQUIREMENT_SPEC,
            True,
            now - timedelta(days=16),
        ),
        ("ui_design", t9_phase["ui_design"], TODO9_UI_DESIGN, True, now - timedelta(days=12)),
        (
            "tech_architecture",
            t9_phase["architecture"],
            TODO9_TECH_ARCHITECTURE,
            True,
            now - timedelta(days=8),
        ),
        ("dev_report", t9_phase["development"], TODO9_DEV_REPORT, True, now - timedelta(days=2)),
    ]
    for art_type, phase_id, content, confirmed, conf_at in t9_artifacts:
        await _insert(
            "artifacts",
            {
                "id": uuid.uuid4(),
                "todo_id": todo9_id,
                "phase_id": phase_id,
                "artifact_type": art_type,
                "content": json.dumps(content),
                "version": 1,
                "is_confirmed": confirmed,
                "confirmed_at": conf_at,
                "created_at": conf_at - timedelta(days=1),
                "updated_at": conf_at,
            },
        )

    # ── Todo10: 个性化推荐算法 (pending) ──

    await _insert(
        "todos",
        {
            "id": todo10_id,
            "user_id": user_id,
            "project_id": project3_id,
            "version_id": ver4_id,
            "title": "个性化推荐算法",
            "description": "基于用户行为数据的协同过滤推荐，首页千人千面和搜索结果个性化排序",
            "status": "pending",
            "priority": 2,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "AI", "color": "#A78BFA"}, {"label": "推荐", "color": "#EC4899"}]
            ),
            "created_at": now - timedelta(days=20),
            "updated_at": now - timedelta(days=1),
        },
    )

    # ═══════════════════════════════════════════════════════════
    # Project 4: 内部OKR管理平台
    # ═══════════════════════════════════════════════════════════

    project4_id = uuid.uuid4()
    ver5_id = uuid.uuid4()
    todo11_id, todo12_id = uuid.uuid4(), uuid.uuid4()
    t11_phase = {
        pt: uuid.uuid4()
        for pt in [
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        ]
    }
    t11_conv = {"clarification": uuid.uuid4()}

    await _insert(
        "projects",
        {
            "id": project4_id,
            "user_id": user_id,
            "name": "内部OKR管理平台",
            "description": "支持目标对齐、进度追踪和复盘的OKR管理工具，替代飞书文档手工管理",
            "tech_stack": "Vue 3 + Go + MySQL + Redis",
            "status": "active",
            "created_at": now - timedelta(days=7),
            "updated_at": now - timedelta(days=1),
        },
    )

    await _insert(
        "versions",
        {
            "id": ver5_id,
            "project_id": project4_id,
            "name": "v1.0",
            "goal": "目标设定与可视化追踪",
            "status": "active",
            "order": 1,
            "created_at": now - timedelta(days=7),
            "updated_at": now - timedelta(days=1),
        },
    )

    # ── Todo11: OKR目标树管理 (active, at clarification) ──

    await _insert(
        "todos",
        {
            "id": todo11_id,
            "user_id": user_id,
            "project_id": project4_id,
            "version_id": ver5_id,
            "title": "OKR目标树管理",
            "description": "可视化目标树，支持O-KR层级展开、进度追踪、上下级对齐关系",
            "status": "active",
            "priority": 1,
            "current_phase": "clarification",
            "tags": json.dumps(
                [{"label": "前端", "color": "#34D399"}, {"label": "核心功能", "color": "#6366F1"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    await _insert(
        "conversations",
        {
            "id": t11_conv["clarification"],
            "todo_id": todo11_id,
            "purpose": "clarification",
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    t11_phases_data = [
        ("clarification", "active", t11_conv["clarification"]),
        ("ui_design", "pending", None),
        ("architecture", "pending", None),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t11_phases_data:
        await _insert(
            "pipeline_phases",
            {
                "id": t11_phase[pt],
                "todo_id": todo11_id,
                "phase_type": pt,
                "status": status,
                "conversation_id": cid,
                "created_at": now - timedelta(days=5),
                "updated_at": now,
            },
        )

    await _insert_messages(t11_conv["clarification"], TODO11_CLAR_MESSAGES, now - timedelta(days=3))

    # ── Todo12: 进度自动同步 (pending) ──

    await _insert(
        "todos",
        {
            "id": todo12_id,
            "user_id": user_id,
            "project_id": project4_id,
            "version_id": ver5_id,
            "title": "进度自动同步",
            "description": "KR进度与Jira/GitLab联动，自动计算完成百分比并同步到目标树",
            "status": "pending",
            "priority": 2,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "后端", "color": "#4A9FD8"}, {"label": "集成", "color": "#F59E0B"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    # ═══════════════════════════════════════════════════════════
    # Project 5: 开发者开放平台 (3 versions, full pipeline)
    # ═══════════════════════════════════════════════════════════

    from .gateway import seed_gateway_project

    gw_result = await seed_gateway_project(db, user_id, now)
    _ = gw_result["project_id"]

    # ═══════════════════════════════════════════════════════════
    # Experiences
    # ═══════════════════════════════════════════════════════════

    todo_map = {"todo1": todo1_id, "todo2": todo2_id, "todo6": todo6_id}
    project_map = {"todo1": project1_id, "todo2": project1_id, "todo6": project2_id}

    exp_ids = []
    for exp in EXPERIENCES_DATA:
        eid = uuid.uuid4()
        exp_ids.append(eid)
        source = exp.pop("source_todo")
        await _insert(
            "experiences",
            {
                "id": eid,
                "user_id": user_id,
                "todo_id": todo_map[source],
                "project_id": project_map[source],
                "title": exp["title"],
                "scope": exp["scope"],
                "status": exp["status"],
                "problem": exp["problem"],
                "solution": exp["solution"],
                "decisions": json.dumps(exp["decisions"]),
                "pitfalls": json.dumps(exp["pitfalls"]),
                "applicable_scenarios": exp["applicable_scenarios"],
                "tags": json.dumps(exp["tags"]),
                "confidence": exp["confidence"],
                "reuse_count": exp["reuse_count"],
                "created_at": now - timedelta(days=14),
                "updated_at": now - timedelta(days=2),
            },
        )
        exp["source_todo"] = source

    # ═══════════════════════════════════════════════════════════
    # Experience Feedback
    # ═══════════════════════════════════════════════════════════

    feedback_data = [
        (exp_ids[0], todo1_id, True),
        (exp_ids[2], todo1_id, True),
        (exp_ids[3], todo1_id, True),
        (exp_ids[0], todo6_id, False),
    ]
    for eid, tid, helpful in feedback_data:
        await _insert(
            "experience_feedback",
            {
                "id": uuid.uuid4(),
                "experience_id": eid,
                "todo_id": tid,
                "helpful": helpful,
                "created_at": now - timedelta(days=3),
                "updated_at": now - timedelta(days=3),
            },
        )
