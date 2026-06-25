from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.planning.entity import DeliverableTracker, Document, PlanningSession
from arc.domain.planning.repository import (
    DeliverableTrackerRepository as DeliverableTrackerRepositoryABC,
)
from arc.domain.planning.repository import (
    DocumentRepository as DocumentRepositoryABC,
)
from arc.domain.planning.repository import (
    PlanningSessionRepository as PlanningSessionRepositoryABC,
)
from arc.domain.planning.value_objects import (
    DeliverableStatus,
    DocumentStatus,
    PlanningStatus,
)
from arc.infrastructure.models.planning import (
    DeliverableTrackerModel,
    DocumentModel,
    PlanningSessionModel,
)


class DocumentRepository(DocumentRepositoryABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, doc: Document) -> Document:
        model = DocumentModel(
            id=doc.id,
            project_id=doc.project_id,
            filename=doc.filename,
            content_type=doc.content_type,
            size=doc.size,
            storage_path=doc.storage_path,
            extracted_text=doc.extracted_text or None,
            parsed_features=doc.parsed_features or None,
            status=doc.status.value,
        )
        self.db.add(model)
        await self.db.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 100,
    ) -> list[Document]:
        result = await self.db.execute(
            select(DocumentModel)
            .where(DocumentModel.project_id == project_id)
            .order_by(DocumentModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, doc: Document) -> None:
        result = await self.db.execute(select(DocumentModel).where(DocumentModel.id == doc.id))
        model = result.scalar_one_or_none()
        if not model:
            return
        model.extracted_text = doc.extracted_text or None
        model.parsed_features = doc.parsed_features or None
        model.status = doc.status.value
        await self.db.flush()

    async def delete(self, doc_id: uuid.UUID) -> bool:
        result = await self.db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: DocumentModel) -> Document:
        return Document(
            id=model.id,
            project_id=model.project_id,
            filename=model.filename,
            content_type=model.content_type,
            size=model.size,
            storage_path=model.storage_path,
            extracted_text=model.extracted_text or "",
            parsed_features=model.parsed_features or [],
            status=DocumentStatus(model.status),
            created_at=model.created_at,
        )


class PlanningSessionRepository(PlanningSessionRepositoryABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: PlanningSession) -> PlanningSession:
        model = PlanningSessionModel(
            id=session.id,
            project_id=session.project_id,
            version_id=session.version_id,
            document_ids=[str(d) for d in session.document_ids],
            constraints=session.constraints or None,
            roadmap=session.roadmap or None,
            conversation_id=session.conversation_id,
            status=session.status.value,
        )
        self.db.add(model)
        await self.db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> PlanningSession | None:
        result = await self.db.execute(
            select(PlanningSessionModel).where(PlanningSessionModel.id == session_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 100,
    ) -> list[PlanningSession]:
        result = await self.db.execute(
            select(PlanningSessionModel)
            .where(PlanningSessionModel.project_id == project_id)
            .order_by(PlanningSessionModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_by_version(self, version_id: uuid.UUID) -> list[PlanningSession]:
        result = await self.db.execute(
            select(PlanningSessionModel)
            .where(PlanningSessionModel.version_id == version_id)
            .order_by(PlanningSessionModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, session: PlanningSession) -> None:
        result = await self.db.execute(
            select(PlanningSessionModel).where(PlanningSessionModel.id == session.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.version_id = session.version_id
        model.document_ids = [str(d) for d in session.document_ids]
        model.constraints = session.constraints or None
        model.roadmap = session.roadmap or None
        model.conversation_id = session.conversation_id
        model.status = session.status.value
        await self.db.flush()

    @staticmethod
    def _to_entity(model: PlanningSessionModel) -> PlanningSession:
        doc_ids = []
        if model.document_ids:
            doc_ids = [uuid.UUID(d) for d in model.document_ids]
        return PlanningSession(
            id=model.id,
            project_id=model.project_id,
            version_id=model.version_id,
            document_ids=doc_ids,
            constraints=model.constraints or {},
            roadmap=model.roadmap or {},
            conversation_id=model.conversation_id,
            status=PlanningStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DeliverableTrackerRepository(DeliverableTrackerRepositoryABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tracker: DeliverableTracker) -> DeliverableTracker:
        model = DeliverableTrackerModel(
            id=tracker.id,
            todo_id=tracker.todo_id,
            required=tracker.required,
            deliverables={k: v.value for k, v in tracker.deliverables.items()},
        )
        self.db.add(model)
        await self.db.flush()
        return tracker

    async def get_by_todo_id(self, todo_id: uuid.UUID) -> DeliverableTracker | None:
        result = await self.db.execute(
            select(DeliverableTrackerModel).where(DeliverableTrackerModel.todo_id == todo_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, tracker: DeliverableTracker) -> None:
        result = await self.db.execute(
            select(DeliverableTrackerModel).where(DeliverableTrackerModel.id == tracker.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.required = tracker.required
        model.deliverables = {k: v.value for k, v in tracker.deliverables.items()}
        await self.db.flush()

    async def upsert(self, tracker: DeliverableTracker) -> DeliverableTracker:
        existing = await self.get_by_todo_id(tracker.todo_id)
        if existing:
            tracker.id = existing.id
            await self.update(tracker)
            return tracker
        return await self.create(tracker)

    @staticmethod
    def _to_entity(model: DeliverableTrackerModel) -> DeliverableTracker:
        deliverables = {}
        if model.deliverables:
            deliverables = {k: DeliverableStatus(v) for k, v in model.deliverables.items()}
        return DeliverableTracker(
            id=model.id,
            todo_id=model.todo_id,
            required=model.required or [],
            deliverables=deliverables,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
