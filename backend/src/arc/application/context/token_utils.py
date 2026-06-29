"""Token estimation helpers for context control and compression."""

from __future__ import annotations

import re

# CJK Unicode ranges for Chinese/Japanese/Korean detection
_CJK_RE = re.compile(r"[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯]")


def estimate_tokens(text: str) -> int:
    """快速 token 估算。

    中文/CJK 字符约 1.5 token/字，英文约 0.25 token/字符。
    混合文本取加权平均。不依赖 tiktoken 等外部库。
    """
    if not text:
        return 0

    total_chars = len(text)
    if total_chars == 0:
        return 0

    cjk_count = len(_CJK_RE.findall(text))
    non_cjk_count = total_chars - cjk_count
    return int(cjk_count * 1.5 + non_cjk_count * 0.25)

