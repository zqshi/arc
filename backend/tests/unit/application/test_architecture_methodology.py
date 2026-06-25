"""architecture_methodology 单测 — DDD 规则校验 + 事件时态 LLM 化。

覆盖 v6.4 #11: 事件名过去时态校验从字面匹配升级为
🟡结构预筛 + 🟢LLM确认 + 降级兜底 范式。
"""
from arc.application.execution.architecture_methodology import (
    _is_past_tense,
    validate_architecture,
)


class TestValidateArchitectureEventsPastTense:
    """事件时态校验: 🟡预筛 + 🟢LLM确认 + 降级兜底。"""

    async def test_past_tense_event_skips_llm(self):
        """事件名明显过去时态 → 预筛通过, 不调 LLM, 无时态 warning。"""
        content = {"event_storming": {"events": [{"name": "OrderCreated"}]}}
        called = []

        async def llm_fn(prompt: str) -> dict:
            called.append(prompt)
            return {"compliant": []}

        result = await validate_architecture(content, llm_review_fn=llm_fn)
        assert called == []
        assert not any("过去时态" in w for w in result.warnings)

    async def test_suspicious_event_llm_compliant_no_warning(self):
        """可疑事件 + LLM 判合规 → 无时态 warning。"""
        content = {"event_storming": {"events": [{"name": "OrderPlace"}]}}

        async def llm_fn(prompt: str) -> dict:
            assert "OrderPlace" in prompt
            return {"compliant": ["OrderPlace"]}

        result = await validate_architecture(content, llm_review_fn=llm_fn)
        assert not any("过去时态" in w for w in result.warnings)

    async def test_suspicious_event_llm_noncompliant_warning(self):
        """可疑事件 + LLM 判不合规 → 时态 warning。"""
        content = {"event_storming": {"events": [{"name": "OrderPlace"}]}}

        async def llm_fn(prompt: str) -> dict:
            return {"compliant": []}

        result = await validate_architecture(content, llm_review_fn=llm_fn)
        assert any("事件「OrderPlace」不是过去时态" in w for w in result.warnings)

    async def test_llm_exception_degrades_to_prefilter(self):
        """LLM 异常 → 降级回退预筛(suspicious 全部视为不合规, 原行为)。"""
        content = {"event_storming": {"events": [{"name": "OrderPlace"}]}}

        async def llm_fn(prompt: str) -> dict:
            raise RuntimeError("LLM down")

        result = await validate_architecture(content, llm_review_fn=llm_fn)
        assert any("事件「OrderPlace」不是过去时态" in w for w in result.warnings)

    async def test_llm_returns_non_dict_degrades(self):
        """LLM 返回非 dict → 降级(全部可疑报警告)。"""
        content = {"event_storming": {"events": [{"name": "OrderPlace"}]}}

        async def llm_fn(prompt: str) -> dict:
            return "not a dict"  # type: ignore[return-value]

        result = await validate_architecture(content, llm_review_fn=llm_fn)
        assert any("事件「OrderPlace」不是过去时态" in w for w in result.warnings)


class TestValidateArchitectureRules:
    """DDD 结构规则校验(纯规则, 无 LLM)。"""

    async def test_missing_core_domain_violation(self):
        """有子域但无核心域 → violation(不通过)。"""
        content = {
            "domain_design": {
                "subdomains": [{"name": "x", "type": "支撑域"}],
            }
        }
        result = await validate_architecture(content, llm_review_fn=None)
        assert any("核心域" in v for v in result.violations)
        assert result.passed is False

    async def test_context_cycle_violation(self):
        """上下文循环依赖 → violation。"""
        content = {
            "domain_design": {
                "context_relations": [
                    {"from": "A", "to": "B", "type": "ACL"},
                    {"from": "B", "to": "A", "type": "ACL"},
                ]
            }
        }
        result = await validate_architecture(content, llm_review_fn=None)
        assert any("循环依赖" in v for v in result.violations)

    async def test_adr_options_below_two_violation(self):
        """ADR 选项 < 2 → violation。"""
        content = {
            "tech_decisions": [
                {"decision": "D", "options_considered": ["only one"], "trade_offs": "x"}
            ]
        }
        result = await validate_architecture(content, llm_review_fn=None)
        assert any("选项" in v for v in result.violations)

    async def test_event_missing_trigger_warning_soft(self):
        """事件缺 trigger/aggregate → warning(soft, 不阻断 passed)。"""
        content = {"event_storming": {"events": [{"name": "OrderCreated"}]}}
        result = await validate_architecture(content, llm_review_fn=None)
        assert any("缺少触发命令或聚合归属" in w for w in result.warnings)
        assert result.passed is True

    async def test_clean_content_passes(self):
        """合规内容 → passed, 无 violation/warning。"""
        content = {
            "domain_design": {
                "subdomains": [{"name": "core", "type": "核心域"}],
            },
            "event_storming": {
                "events": [{"name": "OrderCreated", "trigger": "PlaceOrder", "aggregate": "Order"}],
            },
            "tech_decisions": [
                {"decision": "D", "options_considered": ["a", "b"], "trade_offs": "x vs y"}
            ],
        }
        result = await validate_architecture(content, llm_review_fn=None)
        assert result.passed is True
        assert result.violations == []
        assert result.warnings == []


class TestIsPastTense:
    """_is_past_tense 字面预筛(🟡 预筛基础)。"""

    def test_english_past_tense(self):
        assert _is_past_tense("OrderCreated") is True
        assert _is_past_tense("PaymentCompleted") is True

    def test_chinese_past_tense(self):
        assert _is_past_tense("订单已创建") is True

    def test_not_past_tense(self):
        assert _is_past_tense("OrderPlace") is False
        assert _is_past_tense("CreateOrder") is False
