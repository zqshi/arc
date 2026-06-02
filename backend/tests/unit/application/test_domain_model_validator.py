"""domain_model_validator 单元测试。"""

import pytest

from arc.application.execution.domain_model_validator import validate_domain_model


class TestValidateDomainModelEmpty:
    @pytest.mark.asyncio
    async def test_empty_model_returns_poor(self):
        result = await validate_domain_model({})
        assert result["score"] == 0
        assert result["level"] == "poor"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["category"] == "completeness"

    @pytest.mark.asyncio
    async def test_none_model_returns_poor(self):
        result = await validate_domain_model(None)
        assert result["level"] == "poor"

    @pytest.mark.asyncio
    async def test_model_with_only_empty_aggregates(self):
        result = await validate_domain_model({"aggregates": []})
        assert result["level"] == "poor"

    @pytest.mark.asyncio
    async def test_model_with_only_empty_subdomains(self):
        result = await validate_domain_model({"subdomains": []})
        assert result["level"] == "poor"
