"""Seed data insertion for Project 5: 开发者开放平台

> 行数超限例外: 纯 seed 插入函数, 数据常量已拆分到 gateway_artifacts.py / gateway_messages.py。

3 versions, v1.0/v2.0 each with 2 full-pipeline todos, v3.0 planning.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from arc.seeds.gateway_artifacts import (
    T1_ARCH,
    T1_DEPLOY,
    T1_DEV,
    T1_EXP,
    T1_REQ,
    T1_TEST,
    T1_UI,
    T2_ARCH,
    T2_DEPLOY,
    T2_DEV,
    T2_EXP,
    T2_REQ,
    T2_TEST,
    T2_UI,
    T3_ARCH,
    T3_DEPLOY,
    T3_DEV,
    T3_EXP,
    T3_REQ,
    T3_TEST,
    T3_UI,
    T4_ARCH,
    T4_DEPLOY,
    T4_DEV,
    T4_EXP,
    T4_REQ,
    T4_TEST,
    T4_UI,
)
from arc.seeds.gateway_messages import (
    T1_ARCH_MSGS,
    T1_CLAR_MSGS,
    T1_EXT_MSGS,
    T1_UI_MSGS,
    T2_ARCH_MSGS,
    T2_CLAR_MSGS,
    T2_EXT_MSGS,
    T2_UI_MSGS,
    T3_ARCH_MSGS,
    T3_CLAR_MSGS,
    T3_EXT_MSGS,
    T3_UI_MSGS,
    T4_ARCH_MSGS,
    T4_CLAR_MSGS,
    T4_EXT_MSGS,
    T4_UI_MSGS,
)

# ═══════════════════════════════════════════════════════════════
# Main insertion function
# ═══════════════════════════════════════════════════════════════


async def seed_gateway_project(db: AsyncSession, user_id, now: datetime) -> dict:
    """Insert 开发者开放平台 project with 3 versions, 4 full-pipeline todos + 2 pending."""

    async def _insert(table: str, values: dict) -> None:
        cols = ", ".join(f'"{k}"' if k == "order" else k for k in values.keys())
        params = ", ".join(f":{k}" for k in values.keys())
        await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)

    async def _insert_messages(conv_id, messages, base_time):
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

    # ── IDs ──
    project_id = uuid.uuid4()
    ver1_id, ver2_id, ver3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo1_id, todo2_id, todo3_id, todo4_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo5_id, todo6_id = uuid.uuid4(), uuid.uuid4()

    phases = [
        "clarification",
        "ui_design",
        "architecture",
        "development",
        "testing",
        "deployment",
        "extraction",
    ]
    conv_phases = ["clarification", "ui_design", "architecture", "extraction"]
    agent_phases = ["development", "testing", "deployment"]

    # Phase/conv/agent IDs for todos 1-4
    phase_ids = {}
    conv_ids = {}
    agent_ids = {}
    for t in [todo1_id, todo2_id, todo3_id, todo4_id]:
        phase_ids[t] = {p: uuid.uuid4() for p in phases}
        conv_ids[t] = {p: uuid.uuid4() for p in conv_phases}
        agent_ids[t] = {p: uuid.uuid4() for p in agent_phases}

    # ── Project ──
    await _insert(
        "projects",
        {
            "id": project_id,
            "user_id": user_id,
            "name": "开发者开放平台",
            "description": "面向第三方开发者的API网关平台，支持应用接入、限流熔断、计费统计和实时监控",
            "tech_stack": "Go + gRPC + Redis + Kubernetes + Prometheus",
            "status": "active",
            "created_at": now - timedelta(days=60),
            "updated_at": now,
        },
    )

    # ── Versions ──
    await _insert(
        "versions",
        {
            "id": ver1_id,
            "project_id": project_id,
            "name": "v1.0",
            "goal": "API网关基础能力：限流熔断 + 第三方应用接入",
            "status": "released",
            "order": 1,
            "created_at": now - timedelta(days=60),
            "updated_at": now - timedelta(days=20),
        },
    )
    await _insert(
        "versions",
        {
            "id": ver2_id,
            "project_id": project_id,
            "name": "v2.0",
            "goal": "计费与监控：API调用计费 + 实时监控看板",
            "status": "active",
            "order": 2,
            "created_at": now - timedelta(days=30),
            "updated_at": now,
        },
    )
    await _insert(
        "versions",
        {
            "id": ver3_id,
            "project_id": project_id,
            "name": "v3.0",
            "goal": "开放生态：开发者文档门户 + SDK自动生成",
            "status": "planning",
            "order": 3,
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    # ── Data mapping for the 4 full-pipeline todos ──
    todo_defs = [
        # (todo_id, ver_id, title, desc, tags, time_offset_days, priority)
        (
            todo1_id,
            ver1_id,
            "API限流与熔断",
            "基于令牌桶算法的API限流，支持按应用/接口粒度配置，Sentinel熔断降级",
            [{"label": "后端", "color": "#4A9FD8"}, {"label": "稳定性", "color": "#EF4444"}],
            55,
            1,
        ),
        (
            todo2_id,
            ver1_id,
            "第三方应用接入",
            "开发者注册、应用创建、API Key管理和调用统计看板",
            [{"label": "全栈", "color": "#6366F1"}, {"label": "核心功能", "color": "#F59E0B"}],
            50,
            2,
        ),
        (
            todo3_id,
            ver2_id,
            "API调用计费系统",
            "按量阶梯定价计费，支持预付费/后付费，月度自动账单和余额预警",
            [{"label": "后端", "color": "#4A9FD8"}, {"label": "商业化", "color": "#EC4899"}],
            28,
            1,
        ),
        (
            todo4_id,
            ver2_id,
            "实时监控看板",
            "基于Prometheus+WebSocket的实时API监控，支持全平台和应用级视角",
            [{"label": "全栈", "color": "#34D399"}, {"label": "可观测", "color": "#A78BFA"}],
            25,
            2,
        ),
    ]

    artifact_map = {
        todo1_id: {
            "req": T1_REQ,
            "ui": T1_UI,
            "arch": T1_ARCH,
            "dev": T1_DEV,
            "test": T1_TEST,
            "deploy": T1_DEPLOY,
            "exp": T1_EXP,
        },
        todo2_id: {
            "req": T2_REQ,
            "ui": T2_UI,
            "arch": T2_ARCH,
            "dev": T2_DEV,
            "test": T2_TEST,
            "deploy": T2_DEPLOY,
            "exp": T2_EXP,
        },
        todo3_id: {
            "req": T3_REQ,
            "ui": T3_UI,
            "arch": T3_ARCH,
            "dev": T3_DEV,
            "test": T3_TEST,
            "deploy": T3_DEPLOY,
            "exp": T3_EXP,
        },
        todo4_id: {
            "req": T4_REQ,
            "ui": T4_UI,
            "arch": T4_ARCH,
            "dev": T4_DEV,
            "test": T4_TEST,
            "deploy": T4_DEPLOY,
            "exp": T4_EXP,
        },
    }

    msg_map = {
        todo1_id: {
            "clarification": T1_CLAR_MSGS,
            "ui_design": T1_UI_MSGS,
            "architecture": T1_ARCH_MSGS,
            "extraction": T1_EXT_MSGS,
        },
        todo2_id: {
            "clarification": T2_CLAR_MSGS,
            "ui_design": T2_UI_MSGS,
            "architecture": T2_ARCH_MSGS,
            "extraction": T2_EXT_MSGS,
        },
        todo3_id: {
            "clarification": T3_CLAR_MSGS,
            "ui_design": T3_UI_MSGS,
            "architecture": T3_ARCH_MSGS,
            "extraction": T3_EXT_MSGS,
        },
        todo4_id: {
            "clarification": T4_CLAR_MSGS,
            "ui_design": T4_UI_MSGS,
            "architecture": T4_ARCH_MSGS,
            "extraction": T4_EXT_MSGS,
        },
    }

    # ── Insert todos ──
    for tid, vid, title, desc, tags, offset, priority in todo_defs:
        await _insert(
            "todos",
            {
                "id": tid,
                "user_id": user_id,
                "project_id": project_id,
                "version_id": vid,
                "title": title,
                "description": desc,
                "status": "done",
                "priority": priority,
                "current_phase": "extraction",
                "tags": json.dumps(tags),
                "created_at": now - timedelta(days=offset),
                "updated_at": now - timedelta(days=offset - 14),
            },
        )

    # ── Insert conversations ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        for purpose, cid in conv_ids[tid].items():
            await _insert(
                "conversations",
                {
                    "id": cid,
                    "todo_id": tid,
                    "purpose": purpose,
                    "created_at": now - timedelta(days=offset),
                    "updated_at": now - timedelta(days=offset - 10),
                },
            )

    # ── Insert pipeline phases (without agent_session_id first) ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        for pt in phases:
            cid = conv_ids[tid].get(pt)
            await _insert(
                "pipeline_phases",
                {
                    "id": phase_ids[tid][pt],
                    "todo_id": tid,
                    "phase_type": pt,
                    "status": "confirmed",
                    "conversation_id": cid,
                    "created_at": now - timedelta(days=offset),
                    "updated_at": now - timedelta(days=offset - 12),
                },
            )

    # ── Insert agent sessions ──
    agent_configs = {
        "development": ("openhands", "completed"),
        "testing": ("openhands", "completed"),
        "deployment": ("openhands", "completed"),
    }

    task_contexts = {
        todo1_id: {
            "development": {
                "task": "实现Go令牌桶限流+熔断中间件，Redis Lua脚本原子操作，配置热更新",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "限流和熔断的集成测试和压力测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "K8s部署网关限流服务，配置HPA和Prometheus监控",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo2_id: {
            "development": {
                "task": "实现开发者注册、应用管理、API Key鉴权和调用统计",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "应用接入全流程测试、Key验证性能测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署开发者控制台和统计聚合服务",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo3_id: {
            "development": {
                "task": "实现Kafka计量消费、阶梯定价、账单生成和PDF导出",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "计费精度测试、跨月边界测试、幂等性测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署计费服务和CronJob，配置Kafka consumer group",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
        todo4_id: {
            "development": {
                "task": "实现Prometheus查询服务、WebSocket推送和React监控看板",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "testing": {
                "task": "WebSocket推送性能测试、告警检测测试、大屏兼容性测试",
                "repo_url": "https://github.com/example/api-gateway",
            },
            "deployment": {
                "task": "部署监控看板和WebSocket服务，配置Prometheus recording rules",
                "repo_url": "https://github.com/example/api-gateway",
            },
        },
    }

    result_summaries = {
        todo1_id: {
            "development": {
                "status": "success",
                "files_changed": 7,
                "tests_added": 32,
                "lines_added": 1847,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 32,
                "tests_failed": 0,
                "coverage": "91.3%",
            },
            "deployment": {"status": "success", "services_deployed": 1, "replicas": 3},
        },
        todo2_id: {
            "development": {
                "status": "success",
                "files_changed": 9,
                "tests_added": 38,
                "lines_added": 2341,
                "lines_deleted": 12,
            },
            "testing": {
                "status": "success",
                "tests_passed": 38,
                "tests_failed": 0,
                "coverage": "87.6%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
        todo3_id: {
            "development": {
                "status": "success",
                "files_changed": 8,
                "tests_added": 28,
                "lines_added": 1956,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 28,
                "tests_failed": 0,
                "coverage": "93.1%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
        todo4_id: {
            "development": {
                "status": "success",
                "files_changed": 8,
                "tests_added": 22,
                "lines_added": 1423,
                "lines_deleted": 0,
            },
            "testing": {
                "status": "success",
                "tests_passed": 22,
                "tests_failed": 0,
                "coverage": "86.4%",
            },
            "deployment": {"status": "success", "services_deployed": 2, "replicas": 2},
        },
    }

    for tid, _, _, _, _, offset, _ in todo_defs:
        for phase_name, (agent_type, status) in agent_configs.items():
            aid = agent_ids[tid][phase_name]
            day_offset = {
                "development": offset - 6,
                "testing": offset - 4,
                "deployment": offset - 2,
            }[phase_name]
            await _insert(
                "agent_sessions",
                {
                    "id": aid,
                    "todo_id": tid,
                    "phase_id": phase_ids[tid][phase_name],
                    "agent_type": agent_type,
                    "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
                    "status": status,
                    "task_context": json.dumps(task_contexts[tid][phase_name]),
                    "result_summary": json.dumps(result_summaries[tid][phase_name]),
                    "error_reason": "",
                    "started_at": now - timedelta(days=day_offset),
                    "completed_at": now - timedelta(days=day_offset, hours=-3),
                    "created_at": now - timedelta(days=day_offset),
                    "updated_at": now - timedelta(days=day_offset, hours=-3),
                },
            )

    # ── Link agent sessions to phases ──
    for tid in [todo1_id, todo2_id, todo3_id, todo4_id]:
        for phase_name in agent_phases:
            await db.execute(
                text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
                {"aid": agent_ids[tid][phase_name], "pid": phase_ids[tid][phase_name]},
            )

    # ── Insert messages ──
    for tid, _, _, _, _, offset, _ in todo_defs:
        msgs = msg_map[tid]
        for purpose, messages in msgs.items():
            day_map = {
                "clarification": offset - 1,
                "ui_design": offset - 3,
                "architecture": offset - 5,
                "extraction": offset - 12,
            }
            await _insert_messages(
                conv_ids[tid][purpose], messages, now - timedelta(days=day_map[purpose])
            )

    # ── Insert artifacts ──
    art_type_map = [
        ("requirement_spec", "clarification", "req", 10),
        ("ui_design", "ui_design", "ui", 8),
        ("tech_architecture", "architecture", "arch", 6),
        ("dev_report", "development", "dev", 4),
        ("test_report", "testing", "test", 3),
        ("deploy_report", "deployment", "deploy", 2),
        ("experience_card", "extraction", "exp", 1),
    ]

    for tid, _, _, _, _, offset, _ in todo_defs:
        arts = artifact_map[tid]
        for art_type, phase_name, key, day_delta in art_type_map:
            conf_at = now - timedelta(days=offset - 14 + day_delta)
            await _insert(
                "artifacts",
                {
                    "id": uuid.uuid4(),
                    "todo_id": tid,
                    "phase_id": phase_ids[tid][phase_name],
                    "artifact_type": art_type,
                    "content": json.dumps(arts[key]),
                    "version": 1,
                    "is_confirmed": True,
                    "confirmed_at": conf_at,
                    "created_at": conf_at - timedelta(hours=2),
                    "updated_at": conf_at,
                },
            )

    # ── v3.0 pending todos ──
    await _insert(
        "todos",
        {
            "id": todo5_id,
            "user_id": user_id,
            "project_id": project_id,
            "version_id": ver3_id,
            "title": "开发者文档门户",
            "description": "自动化API文档生成，支持在线调试、代码示例和版本管理",
            "status": "pending",
            "priority": 1,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "前端", "color": "#34D399"}, {"label": "文档", "color": "#6366F1"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    await _insert(
        "todos",
        {
            "id": todo6_id,
            "user_id": user_id,
            "project_id": project_id,
            "version_id": ver3_id,
            "title": "SDK自动生成",
            "description": "基于OpenAPI Spec自动生成多语言SDK（Python/Java/Go），支持类型安全和自动补全",
            "status": "pending",
            "priority": 2,
            "current_phase": None,
            "tags": json.dumps(
                [{"label": "工具链", "color": "#F59E0B"}, {"label": "DX", "color": "#A78BFA"}]
            ),
            "created_at": now - timedelta(days=5),
            "updated_at": now,
        },
    )

    return {
        "project_id": project_id,
        "todo_ids": [todo1_id, todo2_id, todo3_id, todo4_id],
    }
