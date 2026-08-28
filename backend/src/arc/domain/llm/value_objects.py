"""LLM provider 值对象 — 协议族 + 预置模板 (v6.20 L1)。

provider 协议族决定 adapter 构造方式与是否支持在线拉取模型清单:
- OPENAI_COMPATIBLE: 走 OpenAI 兼容协议 (openai/deepseek/ollama/qwen/moonshot/vllm 等),
  支持 client.models.list() 拉取真实模型清单 (免费不计费)。
- ANTHROPIC: 走 Anthropic 协议, 官方无 list models API, 降级为静态建议清单 (诚实标注, 不假装能力)。

PROVIDER_TEMPLATES 是 provider 列表的单一真相源 (替代旧版前端 MODEL_SUGGESTIONS + 后端
llm_factory 硬编码两处不同步)。前端"添加厂商"时选模板快速填默认 base_url, 也可全自定义
(kind=openai_compatible + 任意 base_url)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LLMProviderKind(StrEnum):
    """LLM provider 协议族 — 决定 adapter + 是否支持在线拉取模型清单。"""

    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI 兼容协议 (openai/deepseek/ollama/qwen...)
    ANTHROPIC = "anthropic"  # Anthropic 协议 (官方无 list models API)

    @property
    def supports_list_models(self) -> bool:
        """该协议族是否支持在线拉取模型清单。

        OpenAI 兼容走 client.models.list() (免费不计费);
        Anthropic 官方无 list models API, 降级为静态建议清单。
        """
        return self is LLMProviderKind.OPENAI_COMPATIBLE


@dataclass(frozen=True)
class ProviderTemplate:
    """预置 provider 模板 — 用户"添加厂商"时选模板快速填默认 base_url + 显示名。

    单一真相源, 前后端共享, 替代旧版前端 MODEL_SUGGESTIONS + 后端 llm_factory 硬编码两处。
    用户也可选"自定义"填任意 base_url (kind=openai_compatible)。
    """

    key: str  # 模板标识 (openai/deepseek/anthropic/ollama...)
    label: str  # 显示名
    kind: LLMProviderKind  # 协议族
    default_base_url: str  # 默认 base_url (用户可改; 空=用 SDK 默认端点)
    suggested_models: tuple[str, ...] = ()  # 静态建议模型 (Anthropic 无 list API / verify 前占位)


PROVIDER_TEMPLATES: tuple[ProviderTemplate, ...] = (
    ProviderTemplate(
        key="openai",
        label="OpenAI",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="https://api.openai.com/v1",
        suggested_models=("gpt-4o", "gpt-4o-mini", "o1", "o3-mini"),
    ),
    ProviderTemplate(
        key="deepseek",
        label="DeepSeek",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="https://api.deepseek.com/v1",
        suggested_models=("deepseek-chat", "deepseek-reasoner"),
    ),
    ProviderTemplate(
        key="anthropic",
        label="Anthropic",
        kind=LLMProviderKind.ANTHROPIC,
        default_base_url="",  # Anthropic SDK 默认官方端点, 空=用 SDK 默认
        suggested_models=(
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "claude-haiku-4-5-20251001",
        ),
    ),
    ProviderTemplate(
        key="ollama",
        label="Ollama (本地)",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="http://localhost:11434/v1",
        suggested_models=(),  # 本地实例动态拉取
    ),
    ProviderTemplate(
        key="qwen",
        label="通义千问",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        suggested_models=("qwen-plus", "qwen-max", "qwen-turbo"),
    ),
    ProviderTemplate(
        key="moonshot",
        label="Moonshot (Kimi)",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="https://api.moonshot.cn/v1",
        suggested_models=("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"),
    ),
    ProviderTemplate(
        key="orcarouter",
        label="OrcaRouter",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="https://api.orcarouter.ai/v1",
        suggested_models=("gpt-4o", "gpt-4o-mini"),  # 聚合路由, verify 后在线拉取真实清单
    ),
    ProviderTemplate(
        key="custom",
        label="自定义",
        kind=LLMProviderKind.OPENAI_COMPATIBLE,
        default_base_url="",
        suggested_models=(),
    ),
)


def template_by_key(key: str) -> ProviderTemplate | None:
    """按 key 查模板, 未命中返回 None。"""
    for template in PROVIDER_TEMPLATES:
        if template.key == key:
            return template
    return None
