"""对话模式门禁集成测试 — 验证 artifact_extractor.process_message 端到端接线。

验证核心修复: 产出物必须过质量门禁才标记 PRODUCED (修复"产出即完成"虚假状态)。
用真实 DB + mock LLM 评审，覆盖 free 模式下 requirement_spec 产出的完整链路。
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
async def free_todo_with_tracker(client, db_session):
    """建 free 模式项目 + todo + requirement_spec tracker。"""
    resp = await client.post("/api/projects", json={"name": "门禁集成测试"})
    assert resp.status_code in (200, 201)
    project_id = resp.json()["id"]

    from arc.domain.planning.entity import DeliverableTracker
    from arc.domain.todo.entity import Todo
    from arc.infrastructure.repositories.planning import DeliverableTrackerRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    todo = await TodoRepository(db_session).create(
        Todo(title="门禁测试 todo", project_id=project_id)
    )

    tracker = DeliverableTracker(todo_id=todo.id)
    tracker.initialize(["requirement_spec"])
    await DeliverableTrackerRepository(db_session).create(tracker)
    await db_session.commit()
    return todo


_COMPLETE_REQ = {
    "background": "解决某问题",
    "user_stories": [{"id": "US1", "role": "用户", "priority": "P0"}],
    "acceptance_criteria": [{"id": "AC1"}],
    "boundaries": {"in_scope": ["a"], "out_of_scope": ["b"]},
}


def _deliverable_msg(req_spec: dict) -> str:
    return (
        "[DELIVERABLE:requirement_spec]\n"
        f"```json\n{json.dumps(req_spec, ensure_ascii=False)}\n```\n"
    )


def _patch_gate(monkeypatch, *, passed: bool, score: int):
    from arc.application.execution.conversation_gate import ConversationGateResult

    async def fake(artifact_type, content, *, constraint, prior_artifacts=None,
                   conventions="", llm_review_fn=None):
        return ConversationGateResult(
            passed=passed, score=score, threshold=5,
            checked_layers=["structural", "llm_review"],
        )
    monkeypatch.setattr(
        "arc.application.execution.conversation_gate.evaluate_conversation_gate", fake,
    )


class TestConversationGateIntegration:
    async def test_passed_artifact_marks_produced(self, free_todo_with_tracker, db_session, monkeypatch) -> None:
        _patch_gate(monkeypatch, passed=True, score=8)
        from arc.application.execution.artifact_extractor import ArtifactExtractor
        from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

        todo = free_todo_with_tracker
        extracted = await ArtifactExtractor(db_session).process_message(
            _deliverable_msg(_COMPLETE_REQ), todo.id,
        )
        await db_session.commit()

        assert len(extracted) == 1
        assert extracted[0].content["_quality"]["passed"] is True

        tracker = await DeliverableTrackerRepository(db_session).get_by_todo_id(todo.id)
        assert tracker.deliverables["requirement_spec"].value == "produced"

    async def test_failed_artifact_marks_in_progress(self, free_todo_with_tracker, db_session, monkeypatch) -> None:
        # 门禁不过 → IN_PROGRESS (不虚假标记完成)
        _patch_gate(monkeypatch, passed=False, score=3)
        from arc.application.execution.artifact_extractor import ArtifactExtractor
        from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

        todo = free_todo_with_tracker
        extracted = await ArtifactExtractor(db_session).process_message(
            _deliverable_msg(_COMPLETE_REQ), todo.id,
        )
        await db_session.commit()

        assert extracted[0].content["_quality"]["passed"] is False

        tracker = await DeliverableTrackerRepository(db_session).get_by_todo_id(todo.id)
        # 未通过门禁 → in_progress，绝不 produced
        assert tracker.deliverables["requirement_spec"].value == "in_progress"
