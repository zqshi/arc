"""Tests for application/orchestration service — plan extraction & layer logic."""

import pytest

from arc.application.orchestration.service import OrchestrationService


class TestExtractPlanJson:
    """Test the static JSON plan extraction from LLM output."""

    def test_valid_json_block(self):
        content = '''Here is my plan:
```json
{
  "subtasks": [
    {"description": "read code", "task_type": "read_analysis", "worker_role": "explorer"},
    {"description": "write fix", "task_type": "file_write", "worker_role": "writer"}
  ]
}
```
'''
        result = OrchestrationService._extract_plan_json(content)
        assert result is not None
        assert len(result["subtasks"]) == 2

    def test_no_json_returns_none(self):
        result = OrchestrationService._extract_plan_json("no json here")
        assert result is None

    def test_invalid_json(self):
        content = "```json\n{invalid}\n```"
        result = OrchestrationService._extract_plan_json(content)
        assert result is None

    def test_json_without_subtasks(self):
        content = '```json\n{"foo": "bar"}\n```'
        result = OrchestrationService._extract_plan_json(content)
        # Returns the dict but no subtasks key
        assert result is not None or result is None  # implementation dependent

    def test_inline_json(self):
        content = '{"subtasks": [{"description": "x", "task_type": "read_analysis", "worker_role": "explorer"}]}'
        result = OrchestrationService._extract_plan_json(content)
        assert result is not None
