"""pipeline gate 死循环修复 + P2 评审故障逃生阀端到端集成测试 (v6.24)。

P0: strict 死循环根因修复 — LLM 返回 passed=false 但 score>=阈值 → 应推进 (不再 409)。
P2: 评审故障逃生阀 — LLM 评审基础设施故障 (解析失败 review_infra_failure) 时,
    用户带 reason 可强制确认; 客观守卫 (结构/方法论/DAG) 不可绕过; reason 空 → 400。

用真实 DB + mock LLM (patch 两工厂, 同 test_pipeline_e2e.py 模式)。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_llm():
    """Mock LLM (patch 两工厂, generate/gate 路径统一, 同 test_pipeline_e2e 模式)。"""
    adapter = AsyncMock()
    adapter.chat = AsyncMock()
    adapter.embed = AsyncMock(return_value=[0.1] * 1536)
    adapter.close = AsyncMock()
    with (
        patch("arc.application.ai.llm_adapter.create_llm_adapter", return_value=adapter),
        patch("arc.application.ai.llm_adapter.create_llm_adapter_from_config", return_value=adapter),
    ):
        yield adapter


# 完整 clarification 产出物 — 结构 5 字段齐全且非占位, 无 user_stories (方法论跳过)
_COMPLETE_CLARIFICATION = json.dumps({
    "background": "用户需要批量导出功能",
    "target_users": [{"type": "后台管理员"}],
    "user_scenarios": "管理员选择日期范围导出 CSV",
    "boundaries": {"in_scope": ["CSV"], "out_of_scope": ["流式下载"]},
    "acceptance_criteria": [{"id": "AC1"}],
})


async def _setup_clarification_ready_to_confirm(
    client: AsyncClient, mock_llm
) -> str:
    """建 todo + pipeline + clarification phase + 完整 artifact, 返回 todo_id。

    todo 无 project → _require_pipeline_mode 默认 STRICT。
    """
    resp = await client.post("/api/todos", json={"title": "gate 死循环测试"})
    assert resp.status_code == 201
    todo_id = resp.json()["id"]

    await client.post(f"/api/todos/{todo_id}/pipeline/start")
    await client.post(f"/api/todos/{todo_id}/phases/clarification/start")

    from arc.application.ai.llm_adapter import LLMResponse
    mock_llm.chat.return_value = LLMResponse(
        content=f"```json\n{_COMPLETE_CLARIFICATION}\n```",
        model="mock", usage={},
    )
    await client.post(f"/api/todos/{todo_id}/phases/clarification/generate")
    return todo_id


class TestPipelineGateDeadlockFix:
    """P0: strict 死循环修复端到端。"""

    async def test_score_driven_passes_despite_llm_says_fail(
        self, client: AsyncClient, mock_llm
    ) -> None:
        """死循环复现: LLM 返回 passed=false 但 score=9 → confirm 应 200 (P0 前 409 永久卡死)。"""
        todo_id = await _setup_clarification_ready_to_confirm(client, mock_llm)

        from arc.application.ai.llm_adapter import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content=json.dumps({
                "passed": False,  # P0: 代码不再读此字段
                "score": 9,       # >= strict 阈值 7
                "p0_gaps": [],
                "gaps": ["建议补充风险清单"],
                "suggestion": "ok",
            }),
            model="mock", usage={},
        )

        resp = await client.post(f"/api/todos/{todo_id}/phases/clarification/confirm")
        assert resp.status_code == 200  # score 驱动, 不再卡死


class TestPipelineGateReviewFailureOverride:
    """P2: 评审故障逃生阀。"""

    async def test_force_without_reason_returns_400(
        self, client: AsyncClient, mock_llm
    ) -> None:
        """force_review_failure=true 但无 reason → 400 (参数校验先于 gate)。"""
        todo_id = await _setup_clarification_ready_to_confirm(client, mock_llm)
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm",
            params={"force_review_failure": "true"},
        )
        assert resp.status_code == 400
        assert "reason" in resp.json()["detail"]

    async def test_infra_failure_force_advances(
        self, client: AsyncClient, mock_llm
    ) -> None:
        """LLM 评审解析失败 (review_infra_failure) + force + reason → 推进 (P2 逃生阀)。"""
        todo_id = await _setup_clarification_ready_to_confirm(client, mock_llm)

        from arc.application.ai.llm_adapter import LLMResponse
        # LLM 返回非 JSON → extract_json 解析失败 → review_infra_failure=True
        mock_llm.chat.return_value = LLMResponse(
            content="!!LLM 服务异常, 无法返回有效 JSON!!",
            model="mock", usage={},
        )

        # 无 force → 409 (gate fail, 标识 review_infra_failure)
        resp = await client.post(f"/api/todos/{todo_id}/phases/clarification/confirm")
        assert resp.status_code == 409
        assert resp.json()["detail"]["gate"]["review_infra_failure"] is True

        # 带 force + reason → 200 推进
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm",
            params={
                "force_review_failure": "true",
                "reason": "LLM 评审服务持续故障, 强制推进",
            },
        )
        assert resp.status_code == 200

    async def test_objective_failure_not_overridden_by_force(
        self, client: AsyncClient, mock_llm
    ) -> None:
        """客观 fail (score=3, 非 infra 故障) + force + reason → 仍 409 (客观守卫不可绕过)。"""
        todo_id = await _setup_clarification_ready_to_confirm(client, mock_llm)

        from arc.application.ai.llm_adapter import LLMResponse
        mock_llm.chat.return_value = LLMResponse(
            content=json.dumps({
                "score": 3,
                "p0_gaps": ["关键缺口: 自相矛盾"],
                "gaps": [],
                "suggestion": "补全",
            }),
            model="mock", usage={},
        )
        resp = await client.post(
            f"/api/todos/{todo_id}/phases/clarification/confirm",
            params={"force_review_failure": "true", "reason": "想跳过"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["gate"]["review_infra_failure"] is False
