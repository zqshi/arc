"""代码操作能力 Provider — 声明 AI 可用的代码工具。"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class CodeCapabilityProvider:
    """当项目有本地路径时，注入代码操作工具声明。"""

    source = "code_capability"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo or not request.todo.project_id:
            return []

        try:
            from arc.infrastructure.repositories.project import ProjectRepository
            project = await ProjectRepository(self._db).get_by_id(
                request.todo.project_id
            )
            if not project or not project.local_path:
                return []

            resolved = Path(project.local_path).expanduser().resolve()
            if not resolved.is_dir():
                return []

            content = f"""## 代码操作能力（重要）
你可以直接操作项目代码。项目工作目录: `{resolved}`

可用工具：
- `list_directory` — 查看目录结构，了解项目全貌
- `read_file` — 阅读源码文件，支持指定行范围
- `grep_search` — 搜索代码中的文本/模式
- `run_command` — 执行 shell 命令（git/npm/pytest/ls 等）
- `write_file` — 创建或修改文件

需要了解代码时直接用工具读取，不要让用户贴代码。"""

            return [ContextSegment(
                source=self.source,
                priority=1,
                content=content,
            )]
        except Exception:
            logger.debug("CodeCapabilityProvider failed", exc_info=True)
            return []
