"""LLM-powered codebase analysis — summary + domain model extraction.

Philosophy: goal-driven, LLM-reasoning. We define the intent (what we want
to achieve) and the output interface (so code can parse results). The LLM
decides how to get there — what to focus on, what patterns to recognize,
how to categorize. No prescriptive rules, no step-by-step instructions.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from arc.application.project.scanner import CodebaseScanner, ProjectScale

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt — codebase summary
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

## 项目配置
{config_content}

## 源代码（{source_count} 个文件）
{source_content}
"""

# ---------------------------------------------------------------------------
# Prompt — domain model extraction
# ---------------------------------------------------------------------------

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
    lines = []
    lines.append("### 语言分布")
    lines.append("| 扩展名 | 文件数 |")
    lines.append("|--------|--------|")
    for ext, count in stats["extensions"]:
        lines.append(f"| {ext} | {count} |")

    if stats["top_directories"]:
        lines.append("")
        lines.append("### 代码量 Top 目录")
        lines.append("| 目录 | 代码行数 |")
        lines.append("|------|----------|")
        for dirname, loc in stats["top_directories"]:
            lines.append(f"| {dirname} | {loc} |")

    return "\n".join(lines)


def build_full_prompt(data: dict) -> str:
    scale: ProjectScale = data["scale"]

    config_section = ""
    for fname, content in data["config_files"].items():
        config_section += f"\n### {fname}\n```\n{content}\n```\n"

    source_section = ""
    for fpath, content in data["source_files"].items():
        source_section += f"\n### {fpath}\n```\n{content}\n```\n"

    tree = data["tree"]
    tree_lines = tree.split("\n")
    if len(tree_lines) > 800:
        tree = "\n".join(tree_lines[:800]) + f"\n... (共 {len(tree_lines)} 行)"

    return SCAN_PROMPT.format(
        path=data["path"],
        scale_summary=f"{scale.category} ({scale.file_count} 源文件, {scale.total_loc} 行代码)",
        tree=tree,
        stats=format_stats(data["stats"]),
        config_content=config_section or "(无)",
        source_content=source_section or "(无)",
        source_count=len(data["source_files"]),
    )


def build_domain_model_prompt(data: dict) -> str | None:
    source_files = data.get("source_files", {})
    if not source_files:
        return None

    source_section = ""
    for fpath, content in sorted(source_files.items()):
        source_section += f"\n### {fpath}\n```\n{content}\n```\n"

    return DOMAIN_MODEL_PROMPT.format(source_content=source_section)


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

    model.setdefault("subdomains", [])
    model.setdefault("contexts", [])
    model.setdefault("aggregates", [])
    model.setdefault("relations", [])
    model.setdefault("aggregate_relations", [])
    return model


# ---------------------------------------------------------------------------
# Streaming scan
# ---------------------------------------------------------------------------


async def scan_and_summarize_stream(path: str) -> AsyncIterator[dict]:
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.ai.llm_adapter import LLMMessage

    yield {"event": "stage", "message": "正在遍历项目结构..."}

    scanner = CodebaseScanner(path)
    data = scanner.full_scan()
    scale: ProjectScale = data["scale"]

    yield {
        "event": "stage",
        "message": (
            f"项目规模: {scale.file_count} 个源文件, "
            f"{scale.total_loc} 行代码 ({scale.category}). "
            f"已读取 {len(data['source_files'])} 个文件..."
        ),
    }

    # Pass 1: summary (streamed)
    prompt = build_full_prompt(data)
    yield {"event": "stage", "message": f"AI 正在分析 (~{len(prompt) // 3} tokens)..."}

    full_content = ""
    async with adapter_pool.acquire() as adapter:
        async for chunk in adapter.chat_stream(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.3, max_tokens=scale.max_tokens,
        ):
            full_content += chunk
            yield {"event": "chunk", "content": chunk}

    yield {"event": "done", "summary": full_content}

    # Pass 2: domain model
    dm_prompt = build_domain_model_prompt(data)
    if dm_prompt:
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


async def scan_and_summarize(path: str) -> str:
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.ai.llm_adapter import LLMMessage

    scanner = CodebaseScanner(path)
    data = scanner.full_scan()
    prompt = build_full_prompt(data)

    async with adapter_pool.acquire() as adapter:
        response = await adapter.chat(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.3, max_tokens=data["scale"].max_tokens,
        )
        return response.content
