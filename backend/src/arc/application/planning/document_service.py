"""文档上传、文本提取和Feature解析服务。"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.planning.entity import Document
from arc.domain.planning.value_objects import DocumentStatus
from arc.infrastructure.repositories.planning import DocumentRepository

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get("ARC_UPLOAD_DIR", "uploads/documents")
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/markdown",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)

    async def upload(
        self,
        project_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Document:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"不支持的文件类型: {content_type}")
        if len(data) > MAX_FILE_SIZE:
            raise ValueError("文件大小超过20MB限制")

        doc = Document(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            size=len(data),
        )

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        storage_path = os.path.join(UPLOAD_DIR, f"{doc.id}_{filename}")
        with open(storage_path, "wb") as f:
            f.write(data)
        doc.storage_path = storage_path

        doc.mark_processing()
        await self.doc_repo.create(doc)

        try:
            text = await self._extract_text(storage_path, content_type)
            features = await self._parse_features(text, filename)
            doc.mark_ready(text, features)
        except Exception as exc:
            logger.exception("Document processing failed: %s", exc)
            doc.mark_error()

        await self.doc_repo.update(doc)
        return doc

    async def list_by_project(self, project_id: uuid.UUID) -> list[Document]:
        return await self.doc_repo.list_by_project(project_id)

    async def delete(self, doc_id: uuid.UUID) -> bool:
        doc = await self.doc_repo.get_by_id(doc_id)
        if doc and doc.storage_path and os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
            except OSError:
                pass
        return await self.doc_repo.delete(doc_id)

    async def _extract_text(self, path: str, content_type: str) -> str:
        if content_type in ("text/markdown", "text/plain"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        if content_type == "application/pdf":
            return await self._extract_pdf(path)
        if "wordprocessingml" in content_type:
            return await self._extract_docx(path)
        return ""

    @staticmethod
    async def _extract_pdf(path: str) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("pypdf not installed, PDF text extraction unavailable")
            return "[PDF文件 - 需安装pypdf库进行文本提取]"

    @staticmethod
    async def _extract_docx(path: str) -> str:
        try:
            import docx
            doc = docx.Document(path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            logger.warning("python-docx not installed, DOCX extraction unavailable")
            return "[DOCX文件 - 需安装python-docx库进行文本提取]"

    async def _parse_features(self, text: str, filename: str) -> list[dict]:
        """用AI从文档文本中提取功能点列表。"""
        if not text or len(text.strip()) < 50:
            return []

        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter
        from arc.application.ai.json_extract import extract_json

        prompt = f"""你是一个专业的需求分析师。从以下文档中提取所有功能需求/Feature。

## 文档来源: {filename}
## 文档内容:
{text[:8000]}

## 输出要求
提取所有可独立交付的功能点，输出严格JSON数组：
```json
[
  {{
    "title": "功能名称（简明扼要）",
    "description": "功能描述（1-2句话）",
    "complexity": "S/M/L/XL",
    "category": "功能所属模块/类别",
    "priority_hint": "high/medium/low（基于文档中的描述判断）",
    "dependencies": ["依赖的其他功能title"]
  }}
]
```

注意：
- 每个功能点应该是可独立交付的粒度
- complexity基于你的技术经验估算
- 如果文档中有明确的优先级描述则采用，否则用medium
- dependencies只填文档中提到的显式依赖"""

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat([LLMMessage(role="user", content=prompt)])
        finally:
            await adapter.close()

        result = extract_json(response.content)
        if isinstance(result, list):
            return result
        return []
