"""dev_test_methodology 单测 — 测试结果失败检测 LLM 化。

覆盖 v6.4 #12: "FAIL" in text.upper() 字面匹配升级为
🟡结构预筛 + 🟢LLM确认 + 降级兜底范式(区分测试名/注释中的 FAIL vs 实际失败)。
"""
from arc.application.execution.dev_test_methodology import validate_development


class TestValidateDevelopmentTestFailure:
    """测试结果失败检测: 🟡预筛 + 🟢LLM确认 + 降级兜底。"""

    async def test_no_fail_marker_skips_llm(self):
        """无 FAIL/ERROR 字样 → 不调 LLM, 无失败 gap。"""
        content = {"test_results": "all passed", "code_changes": [{"file": "a.py"}]}
        called = []

        async def llm_fn(prompt: str) -> dict:
            called.append(prompt)
            return {"failed": True}

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert called == []
        assert not any("FAIL/ERROR" in g for g in gaps)

    async def test_fail_marker_llm_confirms_failed(self):
        """含 FAIL + LLM 判真失败 → gap。"""
        content = {"test_results": "FAILED test_x\n1 failed", "code_changes": [{"file": "a.py"}]}

        async def llm_fn(prompt: str) -> dict:
            assert "FAILED test_x" in prompt
            return {"failed": True}

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert any("FAIL/ERROR" in g for g in gaps)

    async def test_fail_in_test_name_llm_confirms_pass(self):
        """FAIL 出现在测试名但实际通过 → LLM 判 false → 无失败 gap。"""
        content = {
            "test_results": "test_should_not_fail passed",
            "code_changes": [{"file": "a.py"}],
        }

        async def llm_fn(prompt: str) -> dict:
            return {"failed": False}

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert not any("FAIL/ERROR" in g for g in gaps)

    async def test_llm_exception_degrades_to_prefilter(self):
        """LLM 异常 → 降级回退字面匹配(报 gap, 原行为)。"""
        content = {"test_results": "FAIL here", "code_changes": [{"file": "a.py"}]}

        async def llm_fn(prompt: str) -> dict:
            raise RuntimeError("LLM down")

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert any("FAIL/ERROR" in g for g in gaps)

    async def test_llm_non_dict_degrades(self):
        """LLM 返回非 dict → 降级(报 gap)。"""
        content = {"test_results": "ERROR here", "code_changes": [{"file": "a.py"}]}

        async def llm_fn(prompt: str) -> dict:
            return "not a dict"  # type: ignore[return-value]

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert any("FAIL/ERROR" in g for g in gaps)

    async def test_missing_failed_field_defaults_to_failed(self):
        """LLM 返回 dict 缺 failed 字段 → 保守视为失败(报 gap)。"""
        content = {"test_results": "FAIL here", "code_changes": [{"file": "a.py"}]}

        async def llm_fn(prompt: str) -> dict:
            return {}

        gaps = await validate_development(content, llm_review_fn=llm_fn)
        assert any("FAIL/ERROR" in g for g in gaps)


class TestValidateDevelopmentStructure:
    """纯结构校验(无 LLM)。"""

    async def test_empty_test_results_gap(self):
        """test_results 为空 → gap。"""
        content = {"test_results": "", "code_changes": [{"file": "a.py"}]}
        gaps = await validate_development(content, llm_review_fn=None)
        assert any("为空" in g for g in gaps)

    async def test_empty_code_changes_gap(self):
        """code_changes 为空 → gap。"""
        content = {
            "test_results": "all passed",
            "code_changes": [],
        }
        gaps = await validate_development(content, llm_review_fn=None)
        assert any("code_changes 为空" in g for g in gaps)

    async def test_clean_content_no_gaps(self):
        """合规内容 → 无 gap。"""
        content = {
            "test_results": "all passed",
            "code_changes": [{"file": "a.py"}],
        }
        gaps = await validate_development(content, llm_review_fn=None)
        assert gaps == []
