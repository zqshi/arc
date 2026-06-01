"""Unit tests for VerifyChain."""

from __future__ import annotations

import pytest

from arc.application.verification.chain import VerifyChain, VerifyContext, VerifyResult


class TestL1SyntaxCheck:
    def test_valid_json_deliverable(self) -> None:
        content = '[DELIVERABLE:requirement_spec]\n```json\n{"background": "x", "user_stories": ["a"], "acceptance_criteria": ["b"], "boundaries": ["c"]}\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_syntax(ctx)
        assert result.passed is True

    def test_invalid_json_deliverable(self) -> None:
        content = '[DELIVERABLE:requirement_spec]\n```json\n{"invalid json\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_syntax(ctx)
        assert result.passed is False
        assert result.level == "L1"
        assert "JSON 解析失败" in result.errors[0]

    def test_unclosed_code_block(self) -> None:
        content = "```python\nprint('hello')\n"  # Missing closing ```
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_syntax(ctx)
        assert result.passed is False
        assert "代码块未闭合" in result.errors[0]

    def test_unmatched_braces(self) -> None:
        content = "{{{{{"  # 5 open, 0 close
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_syntax(ctx)
        assert result.passed is False
        assert "大括号不配对" in result.errors[0]

    def test_normal_text_passes(self) -> None:
        content = "这是一段正常的 AI 输出，没有任何格式问题。"
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_syntax(ctx)
        assert result.passed is True


class TestL2SemanticCheck:
    def test_all_required_fields_present(self) -> None:
        content = '[DELIVERABLE:tech_architecture]\n```json\n{"data_model": "x", "api_design": "y", "tech_decisions": "z"}\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_semantics(ctx)
        assert result.passed is True

    def test_missing_required_fields(self) -> None:
        content = '[DELIVERABLE:tech_architecture]\n```json\n{"data_model": "x"}\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_semantics(ctx)
        assert result.passed is False
        assert result.level == "L2"
        assert "api_design" in result.errors[0]

    def test_empty_required_field(self) -> None:
        content = '[DELIVERABLE:experience_card]\n```json\n{"problem": "", "solution": "y", "decisions": "z"}\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_semantics(ctx)
        assert result.passed is False
        assert "problem" in result.errors[0]

    def test_unknown_deliverable_type_passes(self) -> None:
        content = '[DELIVERABLE:unknown_type]\n```json\n{"anything": "goes"}\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_semantics(ctx)
        assert result.passed is True

    def test_no_deliverable_passes(self) -> None:
        content = "Just regular text without any deliverables."
        ctx = VerifyContext(content=content)
        chain = VerifyChain()
        result = chain._check_semantics(ctx)
        assert result.passed is True


class TestVerifyChainFull:
    @pytest.mark.asyncio
    async def test_all_pass_no_adapter(self) -> None:
        content = "A perfectly normal response."
        ctx = VerifyContext(content=content, user_intent="help me")
        chain = VerifyChain(adapter=None)
        result = await chain.verify(ctx)
        assert result.passed is True
        assert result.level == "ALL"

    @pytest.mark.asyncio
    async def test_l1_failure_stops_chain(self) -> None:
        content = '[DELIVERABLE:requirement_spec]\n```json\n{bad json\n```'
        ctx = VerifyContext(content=content)
        chain = VerifyChain(adapter=None)
        result = await chain.verify(ctx)
        assert result.passed is False
        assert result.level == "L1"
