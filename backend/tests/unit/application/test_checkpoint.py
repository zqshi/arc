"""Unit tests for CheckpointManager — HandoffPackage and pattern extraction."""

from __future__ import annotations

from arc.application.execution.checkpoint import (
    _COMPLETED_PATTERNS,
    _DECISION_PATTERNS,
    _FAILURE_PATTERNS,
    _PENDING_PATTERNS,
    HandoffPackage,
    _extract_file_paths,
    _extract_patterns,
)


class _FakeMsg:
    def __init__(self, content: str, role_value: str = "assistant"):
        self.content = content
        self.role = type("R", (), {"value": role_value})()
        self.metadata = None


class TestHandoffPackage:
    def test_to_dict(self) -> None:
        pkg = HandoffPackage(
            goal="Fix login",
            completed=["auth module"],
            pending=["tests"],
            key_decisions=["use JWT"],
            failed_attempts=["session approach"],
            modified_files=["auth.py"],
            created_at="2026-01-01",
        )
        d = pkg.to_dict()
        assert d["goal"] == "Fix login"
        assert d["completed"] == ["auth module"]
        assert d["modified_files"] == ["auth.py"]

    def test_to_prompt(self) -> None:
        pkg = HandoffPackage(
            goal="Build feature X",
            completed=["step 1"],
            failed_attempts=["bad approach"],
        )
        prompt = pkg.to_prompt()
        assert "Build feature X" in prompt
        assert "step 1" in prompt
        assert "bad approach" in prompt
        assert "不要重复" in prompt

    def test_to_prompt_empty(self) -> None:
        pkg = HandoffPackage(goal="Empty goal")
        prompt = pkg.to_prompt()
        assert "Empty goal" in prompt
        assert "已完成" not in prompt  # No completed section


class TestExtractPatterns:
    def test_extracts_completed(self) -> None:
        msgs = [
            _FakeMsg("已完成用户认证模块的重构"),
            _FakeMsg("下一步是写测试"),
        ]
        results = _extract_patterns(msgs, _COMPLETED_PATTERNS)
        assert len(results) == 1
        assert "认证模块" in results[0]

    def test_extracts_pending(self) -> None:
        msgs = [_FakeMsg("还需要完成数据库迁移")]
        results = _extract_patterns(msgs, _PENDING_PATTERNS)
        assert len(results) == 1
        assert "数据库迁移" in results[0]

    def test_extracts_decisions(self) -> None:
        msgs = [_FakeMsg("决定使用 PostgreSQL 作为主数据库")]
        results = _extract_patterns(msgs, _DECISION_PATTERNS)
        assert len(results) == 1
        assert "PostgreSQL" in results[0]

    def test_extracts_failures(self) -> None:
        msgs = [_FakeMsg("之前尝试用 Redis 缓存但失败了，性能反而更差")]
        results = _extract_patterns(msgs, _FAILURE_PATTERNS)
        assert len(results) == 1
        assert "Redis" in results[0]

    def test_ignores_user_messages(self) -> None:
        msgs = [_FakeMsg("已完成某项工作", "user")]
        results = _extract_patterns(msgs, _COMPLETED_PATTERNS)
        assert len(results) == 0

    def test_deduplicates(self) -> None:
        msgs = [
            _FakeMsg("已完成认证模块"),
            _FakeMsg("已完成认证模块"),  # duplicate
        ]
        results = _extract_patterns(msgs, _COMPLETED_PATTERNS)
        assert len(results) == 1

    def test_skips_short_lines(self) -> None:
        msgs = [_FakeMsg("done")]  # < 5 chars
        results = _extract_patterns(msgs, _COMPLETED_PATTERNS)
        assert len(results) == 0


class TestExtractFilePaths:
    def test_extracts_write_file(self) -> None:
        msgs = [_FakeMsg("write_file: `src/auth.py` 内容如下")]
        paths = _extract_file_paths(msgs)
        assert "src/auth.py" in paths

    def test_extracts_chinese_markers(self) -> None:
        msgs = [_FakeMsg("修改了 src/config.py 中的数据库配置")]
        paths = _extract_file_paths(msgs)
        assert "src/config.py" in paths

    def test_deduplicates_paths(self) -> None:
        msgs = [
            _FakeMsg("修改了 src/main.py"),
            _FakeMsg("又修改了 src/main.py"),
        ]
        paths = _extract_file_paths(msgs)
        assert paths.count("src/main.py") == 1

    def test_empty_messages(self) -> None:
        paths = _extract_file_paths([])
        assert paths == []
