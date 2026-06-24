"""sufficiency 产出门禁集成测试 — v6.0 #7。

验证对话模式 confirm requirement_spec 时, sufficiency 门禁端到端接线:
- 信息不足 → 400 (带 follow_up_questions)
- 信息充分 → 200 (确认成功)
- 非 requirement_spec → 跳过门禁直接确认

用真实 DB + mock LLM (patch create_llm_adapter, 间接 mock resilient adapter)。
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# 与 conftest.TEST_USER_ID 一致 (override_get_current_user 注入的测试用户)
_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_llm():
    """Mock LLM adapter (patch create_llm_adapter, 间接 mock resilient adapter)。"""
    with patch("arc.application.ai.llm_adapter.create_llm_adapter") as factory:
        adapter = AsyncMock()
        adapter.chat = AsyncMock()
        adapter.embed = AsyncMock(return_value=[0.1] * 1536)
        adapter.close = AsyncMock()
        factory.return_value = adapter
        yield adapter


async def _make_todo_with_artifact(
    client: AsyncClient, db_session, *, artifact_type: str, content: dict
):
    """建 project + todo + 指定类型 artifact, 返回 (todo, artifact)。"""
    resp = await client.post("/api/projects", json={"name": "suff门禁测试"})
    assert resp.status_code in (200, 201)
    project_id = resp.json()["id"]

    from arc.domain.artifact.entity import Artifact
    from arc.domain.artifact.value_objects import ArtifactType
    from arc.infrastructure.repositories.artifact import ArtifactRepository
    from arc.domain.todo.entity import Todo
    from arc.infrastructure.repositories.todo import TodoRepository

    todo = await TodoRepository(db_session).create(
        Todo(title="suff测试", project_id=uuid.UUID(project_id)),
        user_id=_TEST_USER_ID,
    )
    artifact = await ArtifactRepository(db_session).create(
        Artifact(
            todo_id=todo.id,
            artifact_type=ArtifactType(artifact_type),
            content=content,
        )
    )
    await db_session.commit()
    return todo, artifact


def _sufficiency_payload(sufficient: bool) -> str:
    return json.dumps({
        "sufficient": sufficient,
        "target_users": {"status": "clear" if sufficient else "missing", "evidence": ""},
        "core_problem": {"status": "clear" if sufficient else "missing", "evidence": ""},
        "feature_direction": {"status": "clear" if sufficient else "missing", "evidence": ""},
        "follow_up_questions": [] if sufficient else ["目标用户是谁?", "要解决什么问题?"],
    }, ensure_ascii=False)


class TestConfirmSufficiencyGate:
    async def test_confirm_blocked_when_insufficient(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        """requirement_spec 信息不足时 confirm 返回 400 (带 follow_up)。"""
        from arc.application.ai.llm_adapter import LLMResponse

        todo, artifact = await _make_todo_with_artifact(
            client, db_session,
            artifact_type="requirement_spec",
            content={"background": "测试需求"},
        )
        mock_llm.chat.return_value = LLMResponse(
            content=_sufficiency_payload(sufficient=False), model="mock", usage={},
        )

        resp = await client.post(
            f"/api/todos/{todo.id}/artifacts/{artifact.id}/confirm"
        )
        assert resp.status_code == 400
        assert "目标用户" in resp.json()["detail"]

    async def test_confirm_passes_when_sufficient(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        """requirement_spec 信息充分时 confirm 返回 200 且确认成功。"""
        from arc.application.ai.llm_adapter import LLMResponse

        todo, artifact = await _make_todo_with_artifact(
            client, db_session,
            artifact_type="requirement_spec",
            content={"background": "测试需求"},
        )
        mock_llm.chat.return_value = LLMResponse(
            content=_sufficiency_payload(sufficient=True), model="mock", usage={},
        )

        resp = await client.post(
            f"/api/todos/{todo.id}/artifacts/{artifact.id}/confirm"
        )
        assert resp.status_code == 200
        assert resp.json()["is_confirmed"] is True

    async def test_non_requirement_spec_skips_gate(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        """非 requirement_spec (如 ui_design) 确认不触发 sufficiency 门禁。"""
        from arc.application.ai.llm_adapter import LLMResponse

        todo, artifact = await _make_todo_with_artifact(
            client, db_session,
            artifact_type="ui_design",
            content={"interaction_design": "测试"},
        )
        # mock 返回 insufficient — 若误触发 gate 会 400
        mock_llm.chat.return_value = LLMResponse(
            content=_sufficiency_payload(sufficient=False), model="mock", usage={},
        )

        resp = await client.post(
            f"/api/todos/{todo.id}/artifacts/{artifact.id}/confirm"
        )
        assert resp.status_code == 200
        assert resp.json()["is_confirmed"] is True
