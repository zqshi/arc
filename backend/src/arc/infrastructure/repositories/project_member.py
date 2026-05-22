from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.models.user import ProjectMemberModel, UserModel


@dataclass
class MemberInfo:
    user_id: uuid.UUID
    display_name: str
    username: str | None
    role: str
    joined_at: datetime


class ProjectMemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = "member",
    ) -> ProjectMemberModel:
        model = ProjectMemberModel(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(model)
        await self.db.flush()
        return model

    async def remove_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            delete(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            )
        )
        return result.rowcount > 0

    async def update_role(self, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> bool:
        result = await self.db.execute(
            select(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.role = role
        await self.db.flush()
        return True

    async def get_member(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectMemberModel | None:
        result = await self.db.execute(
            select(ProjectMemberModel).where(
                and_(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_members(self, project_id: uuid.UUID) -> list[MemberInfo]:
        result = await self.db.execute(
            select(
                ProjectMemberModel.user_id,
                UserModel.display_name,
                UserModel.username,
                ProjectMemberModel.role,
                ProjectMemberModel.created_at,
            )
            .join(UserModel, ProjectMemberModel.user_id == UserModel.id)
            .where(ProjectMemberModel.project_id == project_id)
            .order_by(ProjectMemberModel.created_at)
        )
        return [
            MemberInfo(
                user_id=row.user_id,
                display_name=row.display_name,
                username=row.username,
                role=row.role,
                joined_at=row.created_at,
            )
            for row in result.all()
        ]

    async def list_project_ids_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(ProjectMemberModel.project_id).where(ProjectMemberModel.user_id == user_id)
        )
        return list(result.scalars().all())

    async def is_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(ProjectMemberModel.id)
            .where(
                and_(
                    ProjectMemberModel.project_id == project_id,
                    ProjectMemberModel.user_id == user_id,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
