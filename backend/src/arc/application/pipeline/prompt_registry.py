"""Prompt version management — supports A/B testing and iteration tracking.

Each phase has a versioned prompt. Gate evaluation results are persisted
with a reference to which prompt version produced the artifact.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.application.context.content.phase_prompts import (
    PHASE_EXTRACTION_PROMPTS,
    PHASE_SYSTEM_PROMPTS,
)
from arc.domain.pipeline.value_objects import PhaseType

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    phase_type: PhaseType
    prompt_type: str  # "system" | "extraction" | "gate"
    version: str  # content hash
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:12]


class PromptRegistry:
    """In-memory registry of current prompt versions.

    Tracks which version of each prompt is active. Provides versioning
    info to be stored alongside artifacts and gate results for traceability.
    """

    def __init__(self):
        self._versions: dict[tuple[PhaseType, str], PromptVersion] = {}
        self._initialize()

    def _initialize(self) -> None:
        for phase_type, content in PHASE_SYSTEM_PROMPTS.items():
            version = _content_hash(content)
            self._versions[(phase_type, "system")] = PromptVersion(
                phase_type=phase_type,
                prompt_type="system",
                version=version,
                content=content,
            )

        for phase_type, content in PHASE_EXTRACTION_PROMPTS.items():
            version = _content_hash(content)
            self._versions[(phase_type, "extraction")] = PromptVersion(
                phase_type=phase_type,
                prompt_type="extraction",
                version=version,
                content=content,
            )

    def get_version(self, phase_type: PhaseType, prompt_type: str) -> str:
        key = (phase_type, prompt_type)
        pv = self._versions.get(key)
        return pv.version if pv else "unknown"

    def get_extraction_prompt(self, phase_type: PhaseType) -> str | None:
        key = (phase_type, "extraction")
        pv = self._versions.get(key)
        return pv.content if pv else None



prompt_registry = PromptRegistry()
