"""LLM-powered codebase analysis — summary + domain model extraction.

Handles projects of any size:
  - Small: single-pass, all files in one prompt
  - Large: automatic batched analysis → per-batch summaries → synthesis
  No artificial limits. Adapts to the model's actual context capacity.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from arc.application.project.scanner import CodebaseScanner, ProjectScale

logger = logging.getLogger(__name__)

# Approximate context windows per model family (input tokens).
# Used to decide single-pass vs multi-pass — not a hard cap.
# Chars ÷ 3 ≈ tokens (rough for mixed CJK/ASCII).
_MODEL_CONTEXT_CHARS: dict[str, int] = {
    "gpt-4o": 360_000,       # 128K tokens * ~3
    "gpt-4o-mini": 360_000,
    "deepseek": 360_000,     # 128K
    "claude": 570_000,       # 200K
}
_DEFAULT_CONTEXT_CHARS = 360_000  # conservative default


def _estimate_context_budget() -> int:
    """Get the approximate input-char budget for the current model."""
    from arc.config import get_settings
    try:
        settings = get_settings()
        model = ""
        if settings.llm_provider == "anthropic":
            model = settings.anthropic_model
        elif settings.llm_provider == "deepseek":
            model = settings.deepseek_model
        else:
            model = settings.openai_model

        for prefix, budget in _MODEL_CONTEXT_CHARS.items():
            if prefix in model.lower():
                return budget
    except Exception:
        pass
    return _DEFAULT_CONTEXT_CHARS


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SCAN_PROMPT = """\
阅读以下项目的完整源代码和配置，写一份深度分析报告。

**目标**: 让一个从未见过这个项目的开发者读完你的报告后，能理解项目做什么、怎么构建的、\
如何参与开发。报告的深度和结构由你根据项目的实际情况决定。

---

## 项目路径
{path}

## 项目规模
{scale_summary}

## 目录树
```
{tree}
```

## 统计信息
{stats}

## 源文件（{source_count} 个文件）
{source_content}
"""

BATCH_PROMPT = """\
阅读以下项目文件（第 {batch_num}/{total_batches} 批），提炼这批文件的关键信息。

**目标**: 提取这些文件中的关键架构决策、核心逻辑、API 设计、数据模型、配置要点。
为后续合成完整的项目分析报告提供素材。

## 项目路径
{path}

## 本批文件（{file_count} 个）
{source_content}
"""

SYNTHESIS_PROMPT = """\
以下是对一个项目分批分析后的各批次摘要。请合成一份完整的项目深度分析报告。

**目标**: 让一个从未见过这个项目的开发者读完你的报告后，能理解项目做什么、怎么构建的、\
如何参与开发。报告的深度和结构由你根据项目的实际情况决定。

## 项目路径
{path}

## 项目规模
{scale_summary}

## 目录树
```
{tree}
```

## 统计信息
{stats}

## 各批次分析摘要

{batch_summaries}
"""

DOMAIN_MODEL_PROMPT = """\
阅读以下项目的全部源代码。你的目标是从代码的**实际实现**中，构建一套准确反映该项目\
业务现实的领域模型。

不要从文件名、目录名或注释推断——从代码逻辑本身（类定义、方法行为、状态变迁、\
类型关系、调用链）出发，识别这个项目中真实存在的业务概念、边界和关系。

输出以下 JSON 结构（只输出 JSON）：

```json
{{
  "subdomains": [
    {{"name": "", "type": "核心域|支撑域|通用域", "description": ""}}
  ],
  "contexts": [
    {{"name": "", "subdomain": "", "description": ""}}
  ],
  "aggregates": [
    {{
      "name": "",
      "context": "",
      "description": "",
      "root": "",
      "entities": [],
      "value_objects": [],
      "events": [],
      "methods": [],
      "fields": [],
      "invariants": []
    }}
  ],
  "relations": [
    {{"from": "", "to": "", "type": "", "description": ""}}
  ],
  "aggregate_relations": [
    {{"from": "", "to": "", "type": "", "description": ""}}
  ]
}}
```

---

{source_content}
"""


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_stats(stats: dict) -> str:
    lines = ["### 语言分布", "| 扩展名 | 文件数 |", "|--------|--------|"]
    for ext, count in stats["extensions"]:
        lines.append(f"| {ext} | {count} |")
    if stats["top_directories"]:
        lines += ["", "### 代码量 Top 目录", "| 目录 | 代码行数 |", "|------|----------|"]
        for dirname, loc in stats["top_directories"]:
            lines.append(f"| {dirname} | {loc} |")
    return "\n".join(lines)


def _build_source_section(files: dict[str, str]) -> str:
    parts = []
    for fpath, content in sorted(files.items()):
        parts.append(f"\n### {fpath}\n```\n{content}\n```\n")
    return "".join(parts)


def _split_files_into_batches(
    files: dict[str, str], max_chars_per_batch: int
) -> list[dict[str, str]]:
    """Split files into batches that each fit within the char budget."""
    batches: list[dict[str, str]] = []
    current_batch: dict[str, str] = {}
    current_size = 0

    for fpath, content in sorted(files.items()):
        entry_size = len(fpath) + len(content) + 20  # overhead for markdown formatting
        if current_batch and current_size + entry_size > max_chars_per_batch:
            batches.append(current_batch)
            current_batch = {}
            current_size = 0
        current_batch[fpath] = content
        current_size += entry_size

    if current_batch:
        batches.append(current_batch)
    return batches


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_skeleton(data: dict) -> dict:
    """Build the non-file parts of the prompt (tree, stats, etc.)."""
    scale: ProjectScale = data["scale"]
    tree = data["tree"]
    tree_lines = tree.split("\n")
    if len(tree_lines) > 600:
        tree = "\n".join(tree_lines[:600]) + f"\n... (共 {len(tree_lines)} 行)"
    return {
        "path": data["path"],
        "scale_summary": f"{scale.category} ({scale.file_count} 文件, {scale.total_loc} 行代码)",
        "tree": tree,
        "stats": format_stats(data["stats"]),
    }


def build_full_prompt(data: dict) -> str:
    """Build a single-pass prompt. May exceed model context — caller decides."""
    skeleton = _build_skeleton(data)
    source_section = _build_source_section(data["source_files"])
    return SCAN_PROMPT.format(
        **skeleton,
        source_content=source_section or "(无)",
        source_count=len(data["source_files"]),
    )


def build_domain_model_prompt(data: dict) -> str | None:
    source_files = data.get("source_files", {})
    if not source_files:
        return None
    return DOMAIN_MODEL_PROMPT.format(source_content=_build_source_section(source_files))


def parse_domain_model_response(response_text: str) -> dict | None:
    text = response_text.strip()
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        model = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                model = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Failed to parse domain model JSON")
                return None
        else:
            return None
    for key in ("subdomains", "contexts", "aggregates", "relations", "aggregate_relations"):
        model.setdefault(key, [])
    return model


# ---------------------------------------------------------------------------
# Streaming scan — single-pass or multi-pass depending on size
# ---------------------------------------------------------------------------


async def scan_and_summarize_stream(path: str) -> AsyncIterator[dict]:
    """Stream scan with automatic batching for large projects.

    - If all files fit in one prompt → single LLM call (streamed)
    - If too large → batch analysis → synthesis (each batch streamed)
    """
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.ai.llm_adapter import LLMMessage

    yield {"event": "stage", "message": "正在遍历项目结构..."}

    scanner = CodebaseScanner(path)
    data = scanner.full_scan()
    scale: ProjectScale = data["scale"]

    yield {
        "event": "stage",
        "message": (
            f"项目规模: {scale.file_count} 个文件, "
            f"{scale.total_loc} 行代码 ({scale.category}). "
            f"已读取 {len(data['source_files'])} 个文件..."
        ),
    }

    # Decide: single-pass or multi-pass
    context_budget = _estimate_context_budget()
    skeleton = _build_skeleton(data)
    skeleton_size = sum(len(v) for v in skeleton.values())
    source_section = _build_source_section(data["source_files"])
    total_prompt_size = skeleton_size + len(source_section) + 500  # prompt template overhead

    if total_prompt_size <= context_budget:
        # --- Single-pass: fits in one prompt ---
        yield {"event": "stage", "message": f"AI 正在分析 (~{total_prompt_size // 3000}K tokens)..."}
        full_content = ""
        prompt = SCAN_PROMPT.format(
            **skeleton,
            source_content=source_section,
            source_count=len(data["source_files"]),
        )
        async with adapter_pool.acquire() as adapter:
            async for chunk in adapter.chat_stream(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.3, max_tokens=scale.max_tokens,
            ):
                full_content += chunk
                yield {"event": "chunk", "content": chunk}

        yield {"event": "done", "summary": full_content}

    else:
        # --- Multi-pass: split files into batches ---
        # Reserve space for skeleton in synthesis prompt
        batch_budget = context_budget - skeleton_size - 2000
        batches = _split_files_into_batches(data["source_files"], batch_budget)
        total_batches = len(batches)

        yield {
            "event": "stage",
            "message": f"项目较大，分 {total_batches} 批分析...",
        }

        batch_summaries: list[str] = []

        for i, batch_files in enumerate(batches, 1):
            yield {
                "event": "stage",
                "message": f"分析第 {i}/{total_batches} 批 ({len(batch_files)} 个文件)...",
            }

            batch_prompt = BATCH_PROMPT.format(
                batch_num=i,
                total_batches=total_batches,
                path=data["path"],
                file_count=len(batch_files),
                source_content=_build_source_section(batch_files),
            )

            batch_content = ""
            async with adapter_pool.acquire() as adapter:
                async for chunk in adapter.chat_stream(
                    [LLMMessage(role="user", content=batch_prompt)],
                    temperature=0.3, max_tokens=4096,
                ):
                    batch_content += chunk
                    yield {"event": "chunk", "content": chunk}

            batch_summaries.append(f"### 第 {i} 批 ({len(batch_files)} 个文件)\n{batch_content}")
            yield {"event": "chunk", "content": "\n\n---\n\n"}

        # Synthesis pass
        yield {"event": "stage", "message": "正在合成完整分析报告..."}

        synthesis_prompt = SYNTHESIS_PROMPT.format(
            **skeleton,
            batch_summaries="\n\n".join(batch_summaries),
        )

        full_content = ""
        async with adapter_pool.acquire() as adapter:
            async for chunk in adapter.chat_stream(
                [LLMMessage(role="user", content=synthesis_prompt)],
                temperature=0.3, max_tokens=scale.max_tokens,
            ):
                full_content += chunk
                yield {"event": "chunk", "content": chunk}

        yield {"event": "done", "summary": full_content}

    # --- Domain model extraction (always after summary) ---
    dm_prompt = build_domain_model_prompt(data)
    if dm_prompt:
        dm_prompt_size = len(dm_prompt)
        if dm_prompt_size > context_budget:
            # Domain model also needs batching — use batch summaries as input instead
            if total_prompt_size > context_budget and batch_summaries:
                dm_prompt = DOMAIN_MODEL_PROMPT.format(
                    source_content="\n\n".join(batch_summaries)
                )
            # else: try anyway, let API error be caught

        yield {"event": "stage", "message": "正在构建领域模型..."}
        try:
            async with adapter_pool.acquire() as adapter:
                dm_response = await adapter.chat(
                    [LLMMessage(role="user", content=dm_prompt)],
                    temperature=0.1, max_tokens=8192,
                )
            domain_model = parse_domain_model_response(dm_response.content)
            if domain_model:
                yield {"event": "domain_model", "domain_model": domain_model}
                logger.info(
                    "Domain model: %d sub, %d ctx, %d agg",
                    len(domain_model.get("subdomains", [])),
                    len(domain_model.get("contexts", [])),
                    len(domain_model.get("aggregates", [])),
                )
        except Exception as exc:
            logger.error("Domain model extraction failed: %s", exc)


# ---------------------------------------------------------------------------
# Non-streaming
# ---------------------------------------------------------------------------


async def scan_and_summarize(path: str) -> str:
    """Non-streaming scan. Uses single-pass if fits, otherwise multi-pass."""
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.ai.llm_adapter import LLMMessage

    scanner = CodebaseScanner(path)
    data = scanner.full_scan()
    scale: ProjectScale = data["scale"]
    prompt = build_full_prompt(data)

    context_budget = _estimate_context_budget()
    if len(prompt) <= context_budget:
        async with adapter_pool.acquire() as adapter:
            response = await adapter.chat(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.3, max_tokens=scale.max_tokens,
            )
            return response.content

    # Multi-pass fallback
    result_parts = []
    async for event in scan_and_summarize_stream(data["path"]):
        if event.get("event") == "done":
            return event.get("summary", "")
    return "\n".join(result_parts) or "分析失败"
