"""Robust JSON extraction from LLM responses.

Handles various output formats: raw JSON, markdown-fenced, embedded in text,
and quirks from different model families (OpenAI, Anthropic, DeepSeek).
"""

from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict | list | None:
    """Extract the first valid JSON object/array from LLM output.

    Tries in order:
    1. ```json ... ``` fenced block
    2. ``` ... ``` fenced block (no language tag)
    3. First { ... } or [ ... ] in the text (greedy brace matching)
    4. Raw text as-is
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    for pattern in [
        r"```json\s*\n?(.*?)```",
        r"```\s*\n?(.*?)```",
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            result = _try_parse(candidate)
            if result is not None:
                return result

    result = _try_parse(text)
    if result is not None:
        return result

    result = _extract_by_braces(text)
    if result is not None:
        return result

    return None


def _try_parse(text: str) -> dict | list | None:
    try:
        parsed = json.loads(text, strict=False)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _extract_by_braces(text: str) -> dict | list | None:
    for open_char, close_char in [("{", "}"), ("[", "]")]:
        start = text.find(open_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    result = _try_parse(candidate)
                    if result is not None:
                        return result
                    break
    return None
