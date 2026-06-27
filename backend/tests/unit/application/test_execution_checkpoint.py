"""Checkpoint & HandoffPackage 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass, field

from arc.application.execution.checkpoint import (
    _COMPLETED_PATTERNS,
    _DECISION_PATTERNS,
    _FAILURE_PATTERNS,
    HandoffPackage,
    _extract_file_paths,
    _extract_patterns,
)


@dataclass
class FakeMessage:
    """测试用的消息替身。"""

    role: "FakeRole"
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class FakeRole:
    value: str


ASSISTANT = FakeRole(value="assistant")
USER = FakeRole(value="user")


class TestHandoffPackageCreation:
    def test_minimal(self) -> None:
        pkg = HandoffPackage(goal="完成登录功能")
        assert pkg.goal == "完成登录功能"
        assert pkg.completed == []
        assert pkg.pending == []
        assert pkg.key_decisions == []
        assert pkg.failed_attempts == []
        assert pkg.modified_files == []

    def test_full_fields(self) -> None:
        pkg = HandoffPackage(
            goal="重构支付模块",
            completed=["Step1", "Step2"],
            pending=["Step3"],
            key_decisions=["采用 Stripe"],
            failed_attempts=["PayPal 集成失败"],
            modified_files=["payment.py"],
            created_at="2024-01-01T00:00:00Z",
        )
        assert len(pkg.completed) == 2
        assert "Stripe" in pkg.key_decisions[0]


class TestHandoffPackageToDict:
    def test_round_trip(self) -> None:
        pkg = HandoffPackage(
            goal="test",
            completed=["a"],
            pending=["b"],
        )
        d = pkg.to_dict()
        assert d["goal"] == "test"
        assert d["completed"] == ["a"]
        assert d["pending"] == ["b"]
        assert "created_at" in d


class TestHandoffPackageToPrompt:
    def test_contains_goal(self) -> None:
        pkg = HandoffPackage(goal="实现 SSO 登录")
        prompt = pkg.to_prompt()
        assert "实现 SSO 登录" in prompt
        assert "会话继承摘要" in prompt

    def test_includes_completed(self) -> None:
        pkg = HandoffPackage(goal="goal", completed=["任务A完成了"])
        prompt = pkg.to_prompt()
        assert "已完成" in prompt
        assert "任务A完成了" in prompt

    def test_includes_failed_attempts(self) -> None:
        pkg = HandoffPackage(goal="goal", failed_attempts=["方案X不可行"])
        prompt = pkg.to_prompt()
        assert "失败记录" in prompt
        assert "方案X不可行" in prompt

    def test_includes_modified_files(self) -> None:
        pkg = HandoffPackage(goal="goal", modified_files=["auth.py", "routes.py"])
        prompt = pkg.to_prompt()
        assert "`auth.py`" in prompt
        assert "`routes.py`" in prompt

    def test_empty_sections_omitted(self) -> None:
        pkg = HandoffPackage(goal="goal")
        prompt = pkg.to_prompt()
        assert "已完成" not in prompt
        assert "失败记录" not in prompt


class TestExtractPatterns:
    def test_extracts_completed(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="已完成用户注册模块的开发"),
            FakeMessage(role=ASSISTANT, content="✅ 接口联调通过"),
        ]
        results = _extract_patterns(messages, _COMPLETED_PATTERNS)
        assert len(results) == 2

    def test_ignores_user_messages(self) -> None:
        messages = [
            FakeMessage(role=USER, content="已完成了，对吧？"),
        ]
        results = _extract_patterns(messages, _COMPLETED_PATTERNS)
        assert len(results) == 0

    def test_ignores_short_lines(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="done"),
        ]
        results = _extract_patterns(messages, _COMPLETED_PATTERNS)
        assert len(results) == 0

    def test_deduplicates(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="已完成用户登录"),
            FakeMessage(role=ASSISTANT, content="已完成用户登录"),
        ]
        results = _extract_patterns(messages, _COMPLETED_PATTERNS)
        assert len(results) == 1

    def test_extracts_failure_patterns(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="使用 Redis 方案失败了，换用 PostgreSQL"),
        ]
        results = _extract_patterns(messages, _FAILURE_PATTERNS)
        assert len(results) == 1

    def test_extracts_decision_patterns(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="决定采用 FastAPI 作为 Web 框架"),
        ]
        results = _extract_patterns(messages, _DECISION_PATTERNS)
        assert len(results) == 1


class TestExtractFilePaths:
    def test_extracts_write_file_paths(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="write_file: `src/auth/login.py`"),
            FakeMessage(role=ASSISTANT, content="修改了 routes/api.py 文件"),
        ]
        paths = _extract_file_paths(messages)
        assert "src/auth/login.py" in paths
        assert "routes/api.py" in paths

    def test_deduplicates_paths(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="write_file: auth.py"),
            FakeMessage(role=ASSISTANT, content="write_file: auth.py"),
        ]
        paths = _extract_file_paths(messages)
        assert paths.count("auth.py") == 1

    def test_no_file_paths(self) -> None:
        messages = [
            FakeMessage(role=ASSISTANT, content="这是一段普通文本"),
        ]
        paths = _extract_file_paths(messages)
        assert paths == []
