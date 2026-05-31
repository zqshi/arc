"""Orchestration domain entities.

An ``OrchestrationPlan`` is the ephemeral artifact produced when the
orchestrator LLM decides a task benefits from parallel decomposition.
It holds a DAG of ``Subtask`` items with dependency edges, enabling
topological-sort-based layer execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.orchestration.value_objects import SubtaskType, WorkerRole, WorkerStatus


@dataclass
class Subtask:
    """A single unit of work within an orchestration plan."""

    description: str
    task_type: SubtaskType
    worker_role: WorkerRole
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    context_paths: list[str] = field(default_factory=list)
    depends_on: list[uuid.UUID] = field(default_factory=list)
    status: WorkerStatus = WorkerStatus.PENDING
    result: str = ""
    tokens_used: int = 0
    elapsed_ms: int = 0

    def start(self) -> None:
        self.status = WorkerStatus.RUNNING

    def complete(self, result: str, tokens: int = 0, elapsed_ms: int = 0) -> None:
        self.status = WorkerStatus.COMPLETED
        self.result = result
        self.tokens_used = tokens
        self.elapsed_ms = elapsed_ms

    def fail(self, reason: str) -> None:
        self.status = WorkerStatus.ERROR
        self.result = reason


@dataclass
class OrchestrationPlan:
    """A task decomposition plan produced by the orchestrator.

    Ephemeral — lives for the duration of one response generation.
    Not persisted to database.
    """

    conversation_id: uuid.UUID
    parent_message_id: str
    subtasks: list[Subtask] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: WorkerStatus = WorkerStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def add_subtask(
        self,
        description: str,
        task_type: SubtaskType,
        worker_role: WorkerRole,
        context_paths: list[str] | None = None,
        depends_on: list[uuid.UUID] | None = None,
    ) -> Subtask:
        st = Subtask(
            description=description,
            task_type=task_type,
            worker_role=worker_role,
            context_paths=context_paths or [],
            depends_on=depends_on or [],
        )
        self.subtasks.append(st)
        return st

    def execution_layers(self) -> list[list[Subtask]]:
        """Topological sort into parallelizable layers.

        Each layer contains subtasks whose dependencies are all in
        prior layers. Subtasks within a layer can run concurrently.
        """
        completed_ids: set[uuid.UUID] = set()
        remaining = list(self.subtasks)
        layers: list[list[Subtask]] = []

        while remaining:
            layer = [
                st for st in remaining
                if all(dep in completed_ids for dep in st.depends_on)
            ]
            if not layer:
                # Circular dependency or unresolvable — force remaining into one layer
                layer = remaining
                remaining = []
            else:
                remaining = [st for st in remaining if st not in layer]
            layers.append(layer)
            completed_ids.update(st.id for st in layer)

        return layers

    @property
    def is_complete(self) -> bool:
        return all(
            st.status in (WorkerStatus.COMPLETED, WorkerStatus.ERROR)
            for st in self.subtasks
        )

    @property
    def total_tokens(self) -> int:
        return sum(st.tokens_used for st in self.subtasks)

    def mark_complete(self) -> None:
        self.status = WorkerStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
