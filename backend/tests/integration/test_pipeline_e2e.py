"""E2E Pipeline test — complete flow from todo creation to phase advancement.

Uses a mock LLM adapter to avoid real API calls while testing the full pipeline
orchestration including gate evaluation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

MOCK_CLARIFICATION_ARTIFACT = json.dumps({
    "background": "用户需要一个批量导出功能来处理大量数据",
    "target_users": [
        {"type": "后台管理员", "traits": "日均处理200+数据请求", "core_need": "批量导出用户数据"},
    ],
    "user_scenarios": "管理员在后台选择日期范围，点击导出，系统生成CSV文件",
    "boundaries": {
        "in_scope": ["按日期范围导出", "CSV格式", "支持中文"],
        "out_of_scope": ["自定义列选择（v2考虑）", "实时流式下载"],
        "constraints": ["数据量上限10万行"],
    },
    "acceptance_criteria": [
        {"id": "AC-1", "scenario": "大数据量导出",
         "steps": "选择全量日期范围并导出",
         "expected": "100k行数据耗时<5min", "priority": "P0"},
    ],
    "risk_assessment": [
        {"risk": "大数据量OOM", "probability": "中",
         "impact": "高", "mitigation": "流式写入"},
    ],
})

MOCK_GATE_PASS = json.dumps({
    "passed": True,
    "score": 8,
    "gaps": [],
    "suggestion": "",
})


@pytest.fixture
def mock_llm():
    """Mock LLM that returns predetermined responses."""
    with patch("arc.application.ai.llm_adapter.create_llm_adapter") as mock_factory:
        adapter = AsyncMock()
        adapter.chat = AsyncMock()
        adapter.embed = AsyncMock(return_value=[0.1] * 1536)
        adapter.close = AsyncMock()
        mock_factory.return_value = adapter
        yield adapter


class TestPipelineE2E:
    async def test_full_pipeline_flow(self, client: AsyncClient, mock_llm):
        # 1. Create a todo
        resp = await client.post("/api/todos", json={
            "title": "实现批量数据导出功能",
            "description": "支持管理员按日期范围导出用户数据为CSV",
        })
        assert resp.status_code == 201
        todo_id = resp.json()["id"]

        # 2. Initialize pipeline
        resp = await client.post(f"/api/todos/{todo_id}/pipeline/start")
        assert resp.status_code == 200

        # 3. Verify pipeline state
        resp = await client.get(f"/api/todos/{todo_id}/pipeline")
        assert resp.status_code == 200
        pipeline = resp.json()
        assert len(pipeline["phases"]) == 7
        assert pipeline["current_phase"] == "clarification"

        # 4. Start clarification phase
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/start"
        )
        assert resp.status_code == 200
        phase_data = resp.json()
        assert phase_data["status"] == "active"
        assert phase_data["conversation_id"] is not None

        # 5. Generate artifact (mock LLM returns structured clarification)
        from arc.application.ai.llm_adapter import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content=f"```json\n{MOCK_CLARIFICATION_ARTIFACT}\n```",
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
        )

        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/generate"
        )
        assert resp.status_code == 200

        # 6. Verify artifact was created
        resp = await client.get(f"/api/todos/{todo_id}/pipeline")
        pipeline = resp.json()
        assert len(pipeline["artifacts"]) >= 1
        artifact = pipeline["artifacts"][0]
        assert artifact["artifact_type"] == "requirement_spec"
        assert artifact["content"]["background"] is not None

        # 7. Confirm phase (mock gate passes)
        mock_llm.chat.return_value = LLMResponse(
            content=MOCK_GATE_PASS,
            model="mock-model",
            usage={"prompt_tokens": 50, "completion_tokens": 30},
        )

        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm"
        )
        assert resp.status_code == 200

        # 8. Verify advancement to next phase
        resp = await client.get(f"/api/todos/{todo_id}/pipeline")
        pipeline = resp.json()
        clarification = next(
            p for p in pipeline["phases"] if p["phase_type"] == "clarification"
        )
        assert clarification["status"] == "confirmed"

        ui_design = next(
            p for p in pipeline["phases"] if p["phase_type"] == "ui_design"
        )
        assert ui_design["status"] == "active"

    async def test_gate_blocks_low_quality(self, client: AsyncClient, mock_llm):
        # Create and start
        resp = await client.post("/api/todos", json={"title": "Gate测试任务"})
        todo_id = resp.json()["id"]
        await client.post(f"/api/todos/{todo_id}/pipeline/start")
        await client.post(f"/api/todos/{todo_id}/phases/clarification/start")

        # Generate artifact with minimal content
        from arc.application.ai.llm_adapter import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content=json.dumps({
                "background": "需要做个功能",
                "target_users": [],
                "user_scenarios": "",
                "boundaries": "待补充",
                "acceptance_criteria": "待补充",
                "risk_assessment": "",
            }),
            model="mock-model",
            usage={},
        )
        await client.post(
            f"/api/todos/{todo_id}/phases/clarification/generate"
        )

        # Gate should block — too many empty/placeholder fields
        mock_llm.chat.return_value = LLMResponse(
            content=json.dumps({
                "passed": False,
                "score": 3,
                "gaps": ["target_users列表为空", "acceptance_criteria为占位符"],
                "suggestion": "请补充目标用户和验收标准",
            }),
            model="mock-model",
            usage={},
        )

        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm"
        )
        assert resp.status_code == 409

    async def test_skip_phase(self, client: AsyncClient, mock_llm):
        resp = await client.post("/api/todos", json={"title": "Skip测试"})
        todo_id = resp.json()["id"]
        await client.post(f"/api/todos/{todo_id}/pipeline/start")

        # UI design is skippable
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/ui_design/skip"
        )
        assert resp.status_code == 200

        # Architecture is NOT skippable
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/architecture/skip"
        )
        assert resp.status_code == 400

    async def test_rollback_phase(self, client: AsyncClient, mock_llm):
        resp = await client.post("/api/todos", json={"title": "Rollback测试"})
        todo_id = resp.json()["id"]
        await client.post(f"/api/todos/{todo_id}/pipeline/start")
        await client.post(f"/api/todos/{todo_id}/phases/clarification/start")

        # Generate and confirm clarification
        from arc.application.ai.llm_adapter import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content=MOCK_CLARIFICATION_ARTIFACT,
            model="mock-model",
            usage={},
        )
        await client.post(
            f"/api/todos/{todo_id}/phases/clarification/generate"
        )
        mock_llm.chat.return_value = LLMResponse(
            content=MOCK_GATE_PASS, model="mock-model", usage={}
        )
        await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm"
        )

        # Rollback to clarification
        resp = await client.post(
            f"/api/todos/{todo_id}/pipeline/rollback",
            json={"target_phase": "clarification"},
        )
        assert resp.status_code == 200

        # Verify state
        resp = await client.get(f"/api/todos/{todo_id}/pipeline")
        pipeline = resp.json()
        assert pipeline["current_phase"] == "clarification"
