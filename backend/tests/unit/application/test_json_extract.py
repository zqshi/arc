"""Unit tests for JSON extraction from LLM responses."""

from arc.application.ai.json_extract import extract_json


class TestExtractJson:
    def test_raw_json(self):
        assert extract_json('{"key": "value"}') == {"key": "value"}

    def test_json_with_markdown_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_json_with_bare_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'Here is the result:\n{"score": 8, "passed": true}\nEnd of result.'
        result = extract_json(text)
        assert result == {"score": 8, "passed": True}

    def test_json_array(self):
        text = '```json\n[{"a": 1}, {"b": 2}]\n```'
        result = extract_json(text)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_nested_json(self):
        text = '```json\n{"outer": {"inner": [1, 2, 3]}}\n```'
        result = extract_json(text)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_json_with_chinese(self):
        text = '{"问题": "用户登录失败", "方案": "修复OAuth回调"}'
        result = extract_json(text)
        assert result["问题"] == "用户登录失败"

    def test_json_with_leading_text(self):
        text = "根据分析结果，输出如下：\n\n```json\n{\"passed\": true, \"score\": 9}\n```\n\n以上是评审结果。"
        result = extract_json(text)
        assert result["passed"] is True
        assert result["score"] == 9

    def test_empty_input(self):
        assert extract_json("") is None
        assert extract_json("   ") is None

    def test_no_json(self):
        assert extract_json("This is just plain text with no JSON.") is None

    def test_malformed_json(self):
        assert extract_json('{"key": value}') is None

    def test_json_with_escaped_quotes(self):
        text = '{"message": "He said \\"hello\\""}'
        result = extract_json(text)
        assert result is not None
        assert "hello" in result["message"]

    def test_multiple_json_blocks_returns_first(self):
        text = '```json\n{"first": true}\n```\n\n```json\n{"second": true}\n```'
        result = extract_json(text)
        assert result == {"first": True}

    def test_deepseek_style_with_think_tags(self):
        text = "<think>Let me analyze this...</think>\n\n```json\n{\"result\": \"ok\"}\n```"
        result = extract_json(text)
        assert result == {"result": "ok"}
